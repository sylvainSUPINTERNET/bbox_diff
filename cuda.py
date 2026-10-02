import warp as wp

wp.init()

@wp.kernel
def mul_by_2(
    input: wp.array(dtype=float),
    output: wp.array(dtype=float),
):
    i = wp.tid()  # Indice du thread : 0, 1, 2 ou 3
    output[i] = input[i] * 2.0


# Création des tableaux dans la mémoire du GPU
input = wp.array([1.0, 2.0, 3.0, 4.0], dtype=float, device="cuda:0")
output = wp.zeros(4, dtype=float, device="cuda:0")

# Lancement du kernel pour les 4 éléments
wp.launch(
    kernel=mul_by_2,
    dim=4,
    inputs=[input, output],
    device="cuda:0",
)

# Récupération du résultat sur le CPU
print(output.numpy())  # [2. 4. 6. 8.]