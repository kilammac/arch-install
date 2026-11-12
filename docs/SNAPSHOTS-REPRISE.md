# Snapshots, progression et reprise après échec

## Choix de snapshots

Le questionnaire propose trois options indépendantes du choix des autres logiciels :

- **Aucun** : pas de profil Snapper ni de snapshots automatiques.
- **Manuels** : Snapper configuré pour `/`, un snapshot initial et le nettoyage.
- **Automatiques** : mêmes fonctions, plus `snap-pac` pour les snapshots avant/après
  les transactions Pacman et `snapper-timeline.timer` pour la chronologie.

Rétention configurée : objectif de 10 snapshots numérotés, 5 importants, 3 horaires
et 7 quotidiens. Les paramètres d’âge de Snapper s’appliquent également ; ce n’est
pas une limite stricte du nombre total à chaque instant.

Le profil est écrit directement depuis le modèle Snapper : le sous-volume
`@snapshots` existant n’est ni supprimé ni recréé par `create-config`.

Après installation :

```bash
sudo snapper -c root list
sudo snapper -c root create -c number -d "Avant modification"
```

Ces snapshots couvrent la racine système. `/home`, les journaux, le cache Pacman
et l’état de l’installateur sont des sous-volumes séparés. En UEFI, l’ESP montée
sur `/boot` n’est pas incluse. La cohérence noyaux/modules doit donc être assurée
lors d’une restauration. Aucun menu de démarrage depuis snapshot, ni rollback
automatique de l’ESP, n’est ajouté. Ce n’est pas une sauvegarde externe.

## Barre de progression

La barre reprend le principe de bboysidou : 30 blocs `█/░`, couleur bleue,
compteur `étapes terminées / étapes prévues` et libellé de l’opération. Le total
s’adapte aux snapshots et compléments retenus. Le compteur n’avance qu’après
succès. Les commandes longues gardent leur animation Gum et leur journal.

Lors d’une reprise, le compteur repart du nombre d’étapes déjà terminées. Il ne
s’agit pas du pourcentage d’octets téléchargés par Pacman.

## État durable sur la cible

Le fichier `/var/lib/arch-personnel-install/state.json` contient les réponses,
les IDs des logiciels/configurations, le mode de snapshots, les UUID des
partitions et les étapes terminées/en cours. Il ne contient aucun mot de passe.
Le journal est conservé à côté, dans `install.log`.

Ces fichiers résident dans `@installstate`, séparé de la racine et de ses
snapshots. Les mises à jour du JSON utilisent un fichier temporaire, `fsync`,
puis un remplacement atomique. Sur Btrfs, le fichier est privé (mode 600).

Après échec : relancer le live puis `bash install.sh`. L’outil cherche son état
sur les partitions étiquetées `ArchRoot`, monte uniquement le sous-volume d’état
en lecture seule pour cette recherche, puis propose **Reprendre sans reformater**.

Avant de reprendre, il vérifie les UUID, l’identité du disque, les montages et
sous-volumes attendus, le mode UEFI/BIOS, les réponses et le paquet de
configurations. Un changement de nom `/dev/sda` → `/dev/sdb` est accepté si les
UUID et l’identité correspondent. Une cible différente est refusée.

Les étapes terminées sont conservées. Un échec de pacstrap reprend cette phase ;
une interruption de configuration reprend les opérations restantes. Un compte ou
un lien de configuration déjà créé par une étape partiellement appliquée est
reconnu. Le mot de passe est redemandé uniquement si son étape n’a pas été validée.

## Protéger aussi les réponses avant le premier montage

Avant la création des systèmes de fichiers, aucune cible n’est disponible pour
stocker l’état. Par défaut, les réponses de cette courte phase restent dans le
live et disparaissent à son redémarrage. Pour les conserver dès le questionnaire,
monter une clé USB de données en écriture puis lancer, par exemple :

```bash
bash install.sh --state-dir /run/cle/arch-reprise
```

Le dossier doit être sur un support persistant monté, hors du dépôt et de la
cible. L’installateur refuse un dossier situé uniquement dans la RAM du live.
Garder ce support monté durant l’installation.

Après redémarrage du live, remonter la clé puis utiliser la même option, ou :

```bash
bash install.sh --resume /run/cle/arch-reprise/state.json
```

L’option `--resume` lit le fichier indiqué. Ajouter `--state-dir` pour continuer
à mettre à jour aussi la copie externe ; la copie sur la cible est mise à jour
automatiquement une fois ses partitions reconnues.

Cette copie protège les réponses et le diagnostic, mais n’autorise pas à rejouer
un formatage interrompu. Si l’arrêt survient pendant le partitionnement et qu’une
identité complète de la cible n’a pas encore été enregistrée, la reprise est
bloquée pour inspection manuelle. Ne pas choisir « nouvelle installation » pour
reprendre une phase de logiciels sur un système déjà préparé.

Les anciennes tentatives avec une version dépourvue de journal JSON ne sont pas
récupérées rétroactivement. L’état et les journaux restent locaux ; ils ne doivent
pas être ajoutés à GitHub. Le `.gitignore` les exclut.

Références : [Snapper](https://man.archlinux.org/man/snapper.8.en),
[snap-pac](https://man.archlinux.org/man/extra/snap-pac/snap-pac.8.en),
[configuration Snapper](https://man.archlinux.org/man/snapper-configs.5).

## Erreur « Permission denied » sur postinstall.py

La version corrigée répare aussi une cible déjà déployée : choisir « Arrêter et
conserver la reprise », récupérer la version actuelle de l’installateur, puis
choisir la reprise. Le socle et les configurations terminés restent conservés.

Pour dépanner immédiatement depuis la console root du live, après avoir quitté
le menu en conservant la reprise, les fichiers de la cible sont accessibles ici :

```bash
chmod 755 /mnt/arch-personnel/opt/arch-personnel
chmod 644 /mnt/arch-personnel/opt/arch-personnel/postinstall.py
chmod 644 /mnt/arch-personnel/opt/arch-personnel/options-differees.json
```

Relancer ensuite l’installateur et choisir « Reprendre sans reformater ».
Ne pas appliquer un `chmod -R` général à `/opt` ou au système installé.
