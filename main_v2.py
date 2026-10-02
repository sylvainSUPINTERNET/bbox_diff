import pymupdf


REV0 = "electrical_takeoff_REV_A.pdf"
REV1 = "electrical_takeoff_REV_B.pdf"
OUTPUT = "diff_result.pdf"


# ============================================================
# Utils & Tolérance BBox
# ============================================================

def rects_match(rect1, rect2, tolerance=2.0):
    """
    Vérifie si deux bboxes sont équivalentes avec une tolérance en points.
    """
    r1 = pymupdf.Rect(rect1)
    r2 = pymupdf.Rect(rect2)

    return (
        abs(r1.x0 - r2.x0) <= tolerance and
        abs(r1.y0 - r2.y0) <= tolerance and
        abs(r1.x1 - r2.x1) <= tolerance and
        abs(r1.y1 - r2.y1) <= tolerance
    )


def find_matching_object(target_obj, candidate_objects, bbox_tolerance=2.0):
    """
    Trouve l'objet le plus proche correspondant dans les candidats selon le type,
    le contenu (texte/digest image) et la tolérance de bbox.
    Retourne l'index du candidat correspondant ou None.
    """
    best_idx = None
    best_dist = float("inf")

    for idx, candidate in enumerate(candidate_objects):
        if target_obj["type"] != candidate["type"]:
            continue

        if target_obj["type"] == "text" and target_obj.get("text") != candidate.get("text"):
            continue

        if target_obj["type"] == "image" and target_obj.get("digest") != candidate.get("digest"):
            continue

        r1 = target_obj["rect"]
        r2 = candidate["rect"]

        d_x0 = abs(r1.x0 - r2.x0)
        d_y0 = abs(r1.y0 - r2.y0)
        d_x1 = abs(r1.x1 - r2.x1)
        d_y1 = abs(r1.y1 - r2.y1)

        if (
            d_x0 <= bbox_tolerance and
            d_y0 <= bbox_tolerance and
            d_x1 <= bbox_tolerance and
            d_y1 <= bbox_tolerance
        ):
            dist = max(d_x0, d_y0, d_x1, d_y1)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx

    return best_idx


# ============================================================
# DRAWINGS
# ============================================================

def get_drawings(page):
    result = []

    for d in page.get_drawings():
        rect = pymupdf.Rect(d["rect"])
        result.append({
            "type": "drawing",
            "rect": rect,
        })

    return result


# ============================================================
# TEXT - PAR LIGNE
# ============================================================

def get_text_lines(page):
    result = []

    data = page.get_text("dict")

    for block in data["blocks"]:
        # 0 = text
        if block["type"] != 0:
            continue

        for line in block["lines"]:
            texts = []
            rects = []

            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue

                texts.append(text)
                rects.append(pymupdf.Rect(span["bbox"]))

            if not texts:
                continue

            # Fusion des différents spans de la ligne
            text = " ".join(texts)

            # bbox englobant toute la ligne
            rect = rects[0]
            for r in rects[1:]:
                rect |= r

            result.append({
                "type": "text",
                "text": text,
                "rect": rect,
            })

    return result


# ============================================================
# IMAGES
# ============================================================

def get_images(page):
    result = []

    # hashes=True permet de récupérer digest
    images = page.get_image_info(hashes=True)

    for img in images:
        rect = pymupdf.Rect(img["bbox"])
        digest = img.get("digest")

        result.append({
            "type": "image",
            "rect": rect,
            "digest": digest,
        })

    return result


# ============================================================
# RÉCUPÉRATION DES OBJETS CONFIGURABLE
# ============================================================

def get_objects(page, include_drawings=True, include_text=True, include_images=True):
    """
    Récupère les objets d'une page selon les types activés.
    """
    objects = []
    if include_drawings:
        objects.extend(get_drawings(page))
    if include_text:
        objects.extend(get_text_lines(page))
    if include_images:
        objects.extend(get_images(page))
    return objects


# ============================================================
# DIFF COMPLET CONFIGURABLE
# ============================================================

def diff_pdfs(
    rev0_path=REV0,
    rev1_path=REV1,
    output_path=OUTPUT,
    bbox_tolerance=2.0,
    include_drawings=True,
    include_text=True,
    include_images=True,
):
    """
    Compare deux fichiers PDF et génère un PDF annoté avec les différences.

    :param rev0_path: Chemin du PDF ancienne version.
    :param rev1_path: Chemin du PDF nouvelle version.
    :param output_path: Chemin du PDF de sortie.
    :param bbox_tolerance: Tolérance en points pour le matching des bboxes (ex: 2.0).
    :param include_drawings: Comparer les éléments vectoriels (drawings).
    :param include_text: Comparer le texte.
    :param include_images: Comparer les images.
    """
    rev0 = pymupdf.open(rev0_path)
    rev1 = pymupdf.open(rev1_path)

    for page_number in range(len(rev1)):
        page1 = rev1[page_number]
        print(f"\n========== PAGE {page_number + 1} ==========")

        # Objets ancienne révision
        if page_number < len(rev0):
            page0 = rev0[page_number]
            old_objects = get_objects(
                page0,
                include_drawings=include_drawings,
                include_text=include_text,
                include_images=include_images,
            )
        else:
            old_objects = []

        # Objets nouvelle révision
        new_objects = get_objects(
            page1,
            include_drawings=include_drawings,
            include_text=include_text,
            include_images=include_images,
        )

        # Comparaison avec tolérance
        # Copie pour consommer les objets matchés sans modifier l'original
        remaining_old_objects = list(old_objects)

        for obj in new_objects:
            match_idx = find_matching_object(
                obj,
                remaining_old_objects,
                bbox_tolerance=bbox_tolerance,
            )

            if match_idx is not None:
                # L'objet existait déjà dans REV0
                remaining_old_objects.pop(match_idx)
            else:
                print(
                    "NEW",
                    obj["type"],
                    obj.get("text", ""),
                    obj["rect"],
                )

                # Dessine la différence en BLEU
                page1.draw_rect(
                    obj["rect"],
                    color=(0, 0, 1),
                    width=2,
                )

    rev1.save(
        output_path,
        garbage=4,
        deflate=True,
    )

    rev0.close()
    rev1.close()
    print(f"\nPDF generated: {output_path}")


if __name__ == "__main__":
    # Exemple d'appel configurable :
    # Vous pouvez activer/désactiver drawings, text, images et régler bbox_tolerance
    diff_pdfs(
        rev0_path=REV0,
        rev1_path=REV1,
        output_path=OUTPUT,
        bbox_tolerance=2.0,       # Tolérance en points sur les bboxes (ex: 1.0, 2.0, 5.0...)
        include_drawings=True,     # Activer les tracés vectoriels
        include_text=False,         # Activer le texte (mettre False pour ignorer)
        include_images=False,       # Activer les images (mettre False pour ignorer)
    )