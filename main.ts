import fs from "node:fs";
import * as mupdf from "mupdf";

type Rect = [number, number, number, number];

type DetectOptions = {
  detectText?: boolean;
  detectImages?: boolean;
  detectDrawings?: boolean;
  precision?: number;
};

type PdfObject =
  | {
      type: "text";
      text: string;
      rect: Rect;
      key: string;
    }
  | {
      type: "image";
      rect: Rect;
      key: string;
    }
  | {
      type: "drawing";
      rect: Rect;
      key: string;
    };

const DEFAULT_OPTIONS: Required<DetectOptions> = {
  detectText: true,
  detectImages: true,
  detectDrawings: true,
  precision: 2,
};

export class PdfDiffService {
  private options: Required<DetectOptions>;

  constructor(options: DetectOptions = {}) {
    this.options = {
      ...DEFAULT_OPTIONS,
      ...options,
    };
  }

  // ============================================================
  // Utils
  // ============================================================

  private round(value: number): number {
    const factor = 10 ** this.options.precision;
    return Math.round(value * factor) / factor;
  }

  private rectKey(rect: Rect): string {
    return rect.map((v) => this.round(v)).join(",");
  }

  private normalizeRect(bbox: any): Rect {
    // MuPDF JSON peut exposer bbox sous forme tableau
    // ou éventuellement sous forme { x, y, w, h } selon structure/API.
    if (Array.isArray(bbox)) {
      return [
        bbox[0],
        bbox[1],
        bbox[2],
        bbox[3],
      ];
    }

    if (
      bbox &&
      typeof bbox.x === "number" &&
      typeof bbox.y === "number"
    ) {
      return [
        bbox.x,
        bbox.y,
        bbox.x + (bbox.w ?? 0),
        bbox.y + (bbox.h ?? 0),
      ];
    }

    throw new Error(`Unsupported bbox: ${JSON.stringify(bbox)}`);
  }

  // ============================================================
  // TEXT
  // ============================================================

  private getTextLines(page: mupdf.Page): PdfObject[] {
    const result: PdfObject[] = [];

    /*
     * preserve-spans permet de conserver une structure suffisamment
     * détaillée pour récupérer les lignes / bbox.
     */
    const structuredText =
      page.toStructuredText("preserve-spans");

    const data = JSON.parse(
      structuredText.asJSON(),
    );

    structuredText.destroy();

    for (const block of data.blocks ?? []) {
      if (block.type !== "text") {
        continue;
      }

      for (const line of block.lines ?? []) {
        /*
         * Dans MuPDF.js récent, line.text + line.bbox
         * sont directement disponibles.
         */
        const text = String(
          line.text ?? "",
        ).trim();

        if (!text) {
          continue;
        }

        const rect = this.normalizeRect(line.bbox);

        result.push({
          type: "text",
          text,
          rect,
          key: [
            "text",
            text,
            this.rectKey(rect),
          ].join("|"),
        });
      }
    }

    return result;
  }

  // ============================================================
  // IMAGES
  // ============================================================

  private getImages(page: mupdf.Page): PdfObject[] {
    const result: PdfObject[] = [];

    /*
     * MuPDF StructuredText peut inclure les blocs image.
     *
     * Contrairement à PyMuPDF get_image_info(hashes=True),
     * on n'a pas exactement le même digest directement ici.
     *
     * Pour une première version de ton algo :
     *
     * image + bbox
     *
     * est déjà suffisant.
     */
    const structuredText =
      page.toStructuredText("preserve-images");

    const data = JSON.parse(
      structuredText.asJSON(),
    );

    structuredText.destroy();

    for (const block of data.blocks ?? []) {
      if (block.type !== "image") {
        continue;
      }

      const rect = this.normalizeRect(block.bbox);

      result.push({
        type: "image",
        rect,
        key: [
          "image",
          this.rectKey(rect),
        ].join("|"),
      });
    }

    return result;
  }

  // ============================================================
  // DRAWINGS
  // ============================================================
private getDrawings(page: mupdf.Page): PdfObject[] {
  const result: PdfObject[] = [];

  const device = new mupdf.Device({
    fillPath: (
      path,
      evenOdd,
      ctm,
      colorspace,
      color,
      alpha,
    ) => {
      // Pas de StrokeState pour un fill
      const bbox = path.getBounds(null, ctm);

      const rect: Rect = [
        bbox[0],
        bbox[1],
        bbox[2],
        bbox[3],
      ];

      result.push({
        type: "drawing",
        rect,
        key: [
          "drawing",
          this.rectKey(rect),
        ].join("|"),
      });
    },

    strokePath: (
      path,
      stroke,
      ctm,
      colorspace,
      color,
      alpha,
    ) => {
      // Ici on a bien un StrokeState
      const bbox = path.getBounds(stroke, ctm);

      const rect: Rect = [
        bbox[0],
        bbox[1],
        bbox[2],
        bbox[3],
      ];

      result.push({
        type: "drawing",
        rect,
        key: [
          "drawing",
          this.rectKey(rect),
        ].join("|"),
      });
    },
  });

  page.run(
    device,
    mupdf.Matrix.identity,
  );

  device.close();

  return result;
}

  // ============================================================
  // ALL OBJECTS
  // ============================================================

  private getObjects(page: mupdf.Page): PdfObject[] {
    const result: PdfObject[] = [];

    if (this.options.detectDrawings) {
      result.push(...this.getDrawings(page));
    }

    if (this.options.detectText) {
      result.push(...this.getTextLines(page));
    }

    if (this.options.detectImages) {
      result.push(...this.getImages(page));
    }

    return result;
  }

  // ============================================================
  // DIFF
  // ============================================================

  public detect(
    rev0Path: string,
    rev1Path: string,
  ) {
    const rev0 = mupdf.Document.openDocument(
      fs.readFileSync(rev0Path),
      "application/pdf",
    );

    const rev1 = mupdf.Document.openDocument(
      fs.readFileSync(rev1Path),
      "application/pdf",
    );

    const differences: {
      page: number;
      objects: PdfObject[];
    }[] = [];

    try {
      for (
        let pageNumber = 0;
        pageNumber < rev1.countPages();
        pageNumber++
      ) {
        console.log(
          `========== PAGE ${pageNumber + 1} ==========`,
        );

        const page1 =
          rev1.loadPage(pageNumber);

        let oldObjects: PdfObject[] = [];

        if (pageNumber < rev0.countPages()) {
          const page0 =
            rev0.loadPage(pageNumber);

          oldObjects =
            this.getObjects(page0);

          page0.destroy();
        }

        const newObjects =
          this.getObjects(page1);

        /*
         * Important :
         *
         * on garde une Map<string, number>
         * au lieu d'un Set car plusieurs objets
         * identiques peuvent exister.
         *
         * Equivalent de :
         *
         * old_keys.remove(key)
         *
         * dans ton Python.
         */

        const oldKeys =
          new Map<string, number>();

        for (const obj of oldObjects) {
          oldKeys.set(
            obj.key,
            (oldKeys.get(obj.key) ?? 0) + 1,
          );
        }

        const added: PdfObject[] = [];

        for (const obj of newObjects) {
          const count =
            oldKeys.get(obj.key) ?? 0;

          if (count > 0) {
            if (count === 1) {
              oldKeys.delete(obj.key);
            } else {
              oldKeys.set(
                obj.key,
                count - 1,
              );
            }

            continue;
          }

          added.push(obj);

          console.log(
            "NEW",
            obj.type,
            obj.type === "text"
              ? obj.text
              : "",
            obj.rect,
          );
        }

        differences.push({
          page: pageNumber,
          objects: added,
        });

        page1.destroy();
      }

      return differences;
    } finally {
      rev0.destroy();
      rev1.destroy();
    }
  }
}

const detector = new PdfDiffService({
  detectText: false,
  detectImages: false,
  detectDrawings: true,
});

const differences = detector.detect(
  "electrical_takeoff_REV_A.pdf",
  "electrical_takeoff_REV_B.pdf",
);

console.dir(differences, {
  depth: null,
});