# Dépôt public et installation depuis le live

Ce projet est publié en public sur https://github.com/kilammac/arch-install,
conformément au choix de son propriétaire. Il contient la copie nettoyée de
l’installateur et des configurations. La liste de logiciels, le style du bureau
et ses fonctions sont donc visibles publiquement.

## Lancement direct, comme dans l’installateur de référence

```bash
curl -fsSL https://raw.githubusercontent.com/kilammac/arch-install/main/install/install.sh -o install.sh
bash install.sh
```

Ce fichier télécharge le dépôt complet et lance l’interface Gum. Il n’installe
aucun système sans confirmation du disque cible.

## Depuis le live ISO Arch connecté à Internet

```bash
pacman -Sy --needed git
cd /tmp
git clone --depth 1 https://github.com/kilammac/arch-install.git
cd arch-install
bash install.sh --check
bash install.sh
```

Aucune authentification GitHub n’est nécessaire pour récupérer ce dépôt public.
Le dépôt doit être cloné en entier : scripts, catalogue et `payload/`.
L’installateur demande le compte, les logiciels/configurations et le disque cible,
puis une confirmation précise avant formatage. Le système n’est pas chiffré.

Une fois une version testée avec succès sur disque jetable, créer un tag pour
reproduire cette version via `git clone --depth 1 --branch NOM_DU_TAG URL`.
Une installation et un redémarrage BIOS/LTS ont été validés dans QEMU/KVM.
La session graphique complète et UEFI restent à valider ; les contrôles sont
détaillés dans VALIDATION.md.

## Avant de publier de nouvelles modifications

```bash
python -B audit_publication.py
bash install.sh --check
python -B -m unittest -v test_hardware test_installer test_tui test_session_state test_snapshots test_options_permissions test_package_exclusions
git diff
```

Examiner les fichiers puis créer un commit et pousser. Ne pas ajouter l’ancien
dossier personnel complet, les inventaires ou ses archives. Le `.gitignore`
exclut plusieurs données privées mais ne retire pas un fichier déjà commité.
Les scans de motifs ne garantissent pas l’absence de tous les secrets.

Les fichiers de connexion, historiques et clés ne font pas partie du paquet.
Le lieu de météo/prières est à configurer localement. Le test Fast.com utilise
une variable d’environnement ou un fichier local exclu du dépôt : voir AUDIT.md.
Le `.git` est exclu du transfert vers le système installé.

L’identité Git du projet utilise une adresse GitHub noreply ; la configuration
Git globale du poste n’est pas modifiée.

Sources : [GitHub — accès aux dépôts distants](https://docs.github.com/en/get-started/git-basics/about-remote-repositories),
[GitHub CLI](https://cli.github.com/manual/gh_auth_login).

Le [guide snapshots et reprise](SNAPSHOTS-REPRISE.md) explique aussi comment
reprendre après relance du live, et sauvegarder les réponses sur une clé USB.
