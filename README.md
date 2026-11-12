# arch-install

Installateur Arch Linux x86_64 depuis le live ISO officiel, avec détection du
matériel et sélection des logiciels et configurations. Système non chiffré.

Sur un live connecté à Internet, pour ce dépôt public :

```bash
pacman -Sy --needed git
cd /tmp
git clone --depth 1 https://github.com/kilammac/arch-install.git
cd arch-install
bash install.sh --check
bash install.sh
```

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

Les tests automatisés et le déploiement temporaire passent ; aucun cycle complet
d’installation/redémarrage n’a encore été validé sur une nouvelle machine.
