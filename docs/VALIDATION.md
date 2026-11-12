# Vérification de l’installateur livré

## Vérifications effectuées

- `bash -n install.sh` : syntaxe valide ; 24 scripts embarqués vérifiés sans exécution.
- Syntaxe Python et Lua des sources embarquées vérifiée.
- Lancement normal sur le système actuel : refus attendu avant toute installation.
- `bash install.sh --check` : manifeste des 656 fichiers embarqués valide.
- `python -B -m unittest -v test_hardware test_installer` : 13 tests réussis.
- Profils simulés : AMD double GPU, Intel/NVIDIA, KVM/QEMU, VirtualBox, VMware,
  matériel inconnu et architecture incompatible.
- Garde-fou root/live testé ; refus des disques montés, changements d’identité
  ou de disposition, et sélection identique de racine/ESP.
- Calculs NVMe/SATA/VirtIO et modes UEFI/BIOS testés avec commandes simulées,
  sans aucune commande de partitionnement exécutée.
- Déploiement des vraies configurations dans une cible temporaire : liens,
  Quickshell/cassette, Neovim, clavier français, écran générique, compte cible,
  navigateur disponible, absence des données privées exclues.
- Dépendances du bureau comparées aux index officiels locaux. Les noms sont
  aussi revérifiés dans le live avant toute modification du disque cible.

## Limites réelles

Aucune installation destructive, aucun redémarrage et aucune session Hyprland
sur une nouvelle installation n’ont été effectués. Les tests ne prouvent donc
pas encore le démarrage complet sur ton ASUS ou toutes les VM. Aucun matériel
n’a été modifié pendant cette préparation.

Les paquets et API évoluent : ces configurations viennent de Hyprland 0.57.2 et
Quickshell 0.3.2 sur le système source. Les générations GPU anciennes/inconnues
peuvent demander un choix guidé. Les options AUR peuvent manquer ou échouer à
la compilation ; elles ont une commande de reprise et un bilan séparés.

Le parcours de partitions existantes ne réduit pas Windows. Il exige une ESP
FAT32 de taille suffisante et écrit des fichiers de démarrage dans cette ESP.
Snapper installé ne signifie pas qu’un rollback automatique est configuré.

## Recette encore nécessaire sur disque jetable

Installation et reboot UEFI, installation BIOS en VM, conservation de partitions
existantes, Linux/LTS, bureau complet, réseau, audio, écrans et veille. Documenter
les résultats sur les machines réellement utilisées avant de généraliser.
