# arch-install

Installateur Arch Linux x86_64 depuis le live ISO officiel, avec détection du
matériel et sélection des logiciels et configurations. Système non chiffré.

Lancement direct depuis le live, sur le même principe que l’installateur de
[bboysidou](https://github.com/bboysidou/dotfile_hyperland) :

```bash
curl -fsSL https://raw.githubusercontent.com/kilammac/arch-install/main/install/install.sh -o install.sh
bash install.sh
```

Le lanceur récupère le dossier complet, prépare Gum puis ouvre le parcours guidé :
identité et langue, familles logicielles, réglage fin des paquets, configurations,
shell, chargeur, disque et résumé avant confirmation. Les opérations affichent
leur progression et conservent un journal dans `/run/arch-personnel/install.log`.
Dans Gum : flèches pour naviguer, `x` pour cocher et Entrée pour valider.

Depuis un clone local :

```bash
pacman -Sy --needed git
cd /tmp
git clone --depth 1 https://github.com/kilammac/arch-install.git
cd arch-install
bash install.sh --check
bash install.sh
```

Pour essayer uniquement les menus sur un système existant (sans installation,
sans montage, sans écriture de plan), avec Gum et Python déjà disponibles :

```bash
bash install.sh --preview
```

`--dry-run` est un alias de cet aperçu. Il ne simule pas une installation complète.

Les scripts doivent provenir de ton dépôt de confiance. Pour une version stable,
cloner un tag de release que tu as testé plutôt qu’une branche changeante.

Le programme présente le matériel, le compte à créer, les cases à cocher, puis le
disque. Le mode `effacer` efface le disque entier après confirmation. Le mode
`partitions` utilise des partitions déjà préparées en UEFI, formate la racine
choisie et ajoute des fichiers sur l’ESP conservée. Aucune réduction Windows.

Prérequis : x86_64, réseau, racine de 40 Gio minimum. En mode partitions existantes,
ESP FAT32 GPT de 1 Gio minimum, avec 700 Mio libres. Le mode d’effacement prend
en charge UEFI/systemd-boot et BIOS/GRUB. Secure Boot doit être désactivé.

Le bureau Hyprland/Quickshell et les configurations sont embarqués dans `payload/`.
Les écrans et le clavier sont adaptés à la cible. Les comptes et secrets restent
à configurer localement. Le lieu de météo/prières est à régler après installation.
Le test Fast.com utilise désormais une variable ou un fichier local non publié,
voir [l’audit et les différences](docs/AUDIT.md).

Après installation, se connecter au compte créé sur tty1. Le bureau démarre si
sélectionné ; `start-desktop` le lance manuellement. `arch-options` reprend les
compléments AUR avec le compte ordinaire.

- [Publier et récupérer le dépôt](docs/GITHUB.md)
- [Audit et limites](docs/AUDIT.md)
- [Vérification de l’installateur](docs/VALIDATION.md)

19 tests automatisés passent. Une installation et un redémarrage BIOS/LTS ont
réussi dans QEMU/KVM sur disque jetable. La session graphique complète et le
parcours UEFI restent à valider ; voir les limites dans VALIDATION.md.

## Correction AMD

L’ancien nom `libva-mesa-driver` ne doit pas être exigé comme paquet séparé :
la pile AMD utilise `mesa` et `vulkan-radeon`. L’installateur corrige aussi les
anciens aperçus qui contiendraient encore ce nom. La vérification des paquets
reste effectuée avant toute modification des partitions.

## Différences avec la référence

L’interface utilise Gum et reprend le parcours par étapes et familles de logiciels.
Le moteur Python de détection/déploiement est conservé avec ses validations.
Les scénarios disque sont effacement automatique ou partitions déjà préparées ;
la création automatique dans l’espace non partitionné (alongside) et Limine ne
sont pas proposés. Il n’y a pas de reprise automatique du formatage après erreur.
