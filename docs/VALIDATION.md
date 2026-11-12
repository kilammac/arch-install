# Vérification de l’installateur livré

## Vérifications effectuées

- `bash -n install.sh` : syntaxe valide ; 24 scripts embarqués vérifiés sans exécution.
- Syntaxe Python et Lua des sources embarquées vérifiée.
- Lancement normal sur le système actuel : refus attendu avant toute installation.
- `bash install.sh --check` : manifeste des 656 fichiers embarqués valide.
- `python -B -m unittest -v test_hardware test_installer test_tui test_session_state test_snapshots` : 31 tests réussis.
- Régression AMD : aucun paquet distinct `libva-mesa-driver` exigé ; ancien nom
  normalisé vers `mesa` avant résolution.
- Familles de logiciels et réglage fin testés, présélections Gum vérifiées
  dans un vrai pseudo-terminal ; progression Gum également essayée.
- Aperçu vérifié sans appel aux commandes d’installation.
- Réessai proposé uniquement pour certaines commandes ; jamais pour le formatage.
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

Une recette supplémentaire a été effectuée le 12 novembre 2026 dans QEMU/KVM,
avec l’ISO officiel Arch 2026.11.01 et un disque virtuel jetable de 48 Gio :

- Partitionnement GPT/BIOS, Btrfs et sous-volumes réellement créés.
- 594 paquets installés par pacstrap, comprenant les dépendances des configurations.
- Compte, locale, sudo, initramfs, GRUB et services configurés ; fstab vérifié.
- Configurations personnelles déployées ; fichier du lecteur cassette présent.
- VM arrêtée, live CD retiré, démarrage depuis le disque installé réussi.
- Connexion au compte de recette sur console série, racine Btrfs montée depuis
  `/dev/vda2[/@]`, noyau LTS `6.18.62-1-lts`.
- `Hyprland --version` et `qs --version` exécutés : 0.57.2 et 0.3.2.
- Aucun service en échec dans `systemctl --failed` lors de ce contrôle.

La recette appelle les fonctions du moteur avec des réponses de test, sans
validation manuelle du questionnaire complet. Un accès série et un mot de passe
aléatoire de recette ont été utilisés uniquement dans la VM. Des archives de
paquets déjà en cache sur le poste ont accéléré le téléchargement ; les paquets
restent vérifiés par Pacman. Aucun disque physique du poste n’a été modifié.

La session graphique complète, l’installation UEFI et le matériel ASUS réel n’ont
pas encore été validés dans cette recette. Le chemin BIOS/LTS est le démarrage
réel testé ; les cas AMD sont couverts par les tests de détection/résolution.

Les paquets et API évoluent : ces configurations viennent de Hyprland 0.57.2 et
Quickshell 0.3.2 sur le système source. Les générations GPU anciennes/inconnues
peuvent demander un choix guidé. Les options AUR peuvent manquer ou échouer à
la compilation ; elles ont une commande de reprise et un bilan séparés.

Le parcours de partitions existantes ne réduit pas Windows. Il exige une ESP
FAT32 de taille suffisante et écrit des fichiers de démarrage dans cette ESP.
Snapper installé ne signifie pas qu’un rollback automatique est configuré.

## Recette encore nécessaire sur disque jetable

Installation et reboot UEFI, conservation de partitions existantes, noyau standard,
bureau complet, réseau/audio de session, écrans et veille sur matériel réel. Documenter
les résultats sur les machines réellement utilisées avant de généraliser.

## Reprise et snapshots — recette supplémentaire

Sur une surcouche QEMU jetable de l’installation BIOS déjà testée :

- Création du sous-volume `@installstate` et enregistrement de réponses/UUID réels.
- Échec injecté après un déploiement partiel, avec 7 étapes validées.
- Arrêt complet puis nouveau démarrage du live ISO, donc perte de sa RAM et de `/run`.
- Découverte de l’état sur le disque, même identifiant de session et mêmes réponses.
- Appel du vrai `main()` avec choix de reprise automatisé : aucun appel aux
  formateurs/partitionneurs, à pacstrap ou à la saisie de mot de passe validée.
- Reprise du déploiement, configuration réelle de Snapper et de ses minuteurs,
  création d’un snapshot initial, vérification des images et du fstab.
- Barre à 7/11 à la reprise, puis 11/11 à la fin ; état final `finished=true`.
- Un deuxième appel de création initiale ne crée pas de doublon.
- Copie externe du JSON et du journal essayée sur un volume FAT32 en boucle,
  représentant le système de fichiers d’une clé USB ; sauvegarde et relecture réussies.

Les tests unitaires couvrent également le formatage interrompu refusé, les UUID
résolus sous un autre nom de périphérique, le changement d’identité refusé,
les montages incohérents, la copie externe sur RAM/support en lecture seule
refusée, et la réexécution d’un compte/déploiement partiellement créé.

Cette recette vérifie la reprise depuis un état de nouvelle version. Elle ne
reconstitue pas les états absents des versions antérieures. La compatibilité
UEFI et les restaurations de snapshots avec ESP séparée restent à éprouver.
