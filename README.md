https://nvidia.github.io/warp/stable/user_guide/installation.html

| Terme | Dans cet exemple |
|---|---|
| **Thread** | Un travailleur : le thread `i` calcule `sortie[i] = entree[i] * 2` |
| **Bloc** | Tu regroupes tes travailleurs : **256 threads par bloc** |
| **Grid** | L’ensemble du lancement : **4 blocs**, donc 1 024 threads |
| **Warp** | À l’intérieur de chaque bloc, le GPU fait avancer les threads **par groupes de 32** |