# Installation automatique après préparation

Depuis le live ISO, le parcours demande les informations du système, les logiciels,
les configurations, les snapshots et le comportement final : rester sur le live
ou redémarrer automatiquement. Les mots de passe utilisateur et root sont saisis
de façon masquée, chacun avec confirmation, avant de lancer l’installation.

La confirmation explicite du disque reste obligatoire. Ensuite, l’installation
du système, du bureau et des options AUR sélectionnées avance sans autre saisie.
Le redémarrage n’est exécuté qu’après réussite et si choisi au début.

## Paquets officiels et yay

`pacstrap` fonctionne sans son option interactive. Si nécessaire, yay est construit
comme utilisateur ordinaire avec `makepkg -si --needed --noconfirm`.

Le mode automatique de yay utilise `--noconfirm`, répond `None` aux menus de
nettoyage préalable, de différences et d’édition, et active `--removemake` pour
retirer les dépendances de compilation devenues inutiles. Les vérifications
d’intégrité et de signatures des paquets restent actives. Les entrées standard
des constructions sont fermées pour éviter d’attendre une réponse cachée.

Pendant cette phase uniquement, le compte créé reçoit une règle sudo temporaire
pour `/usr/bin/pacman` et `/usr/bin/mkinitcpio`. Les compilations tournent avec
`runuser`, sans privilèges root. Aucun mot de passe n’est transmis à yay ou sudo.
Le mode sudo non interactif échoue si son autorisation manque.

La règle est validée par `visudo`, puis retirée dans un bloc `finally`, même si
la construction échoue ou est interrompue. Elle est également retirée à la reprise
et à la vérification finale. Une règle `tmpfiles.d` la supprime au démarrage du
système cible en cas de coupure brutale. Le sudo habituel du groupe wheel conserve
sa demande de mot de passe après installation.

L’outil `arch-options` lancé manuellement après démarrage conserve son parcours
interactif. L’option interne `--unattended` est utilisée par l’installateur du live
avec l’autorisation temporaire ; elle n’accorde pas de privilèges à elle seule.

## Mots de passe et reprise

Les mots de passe restent dans la mémoire du programme jusqu’à leur application
par `chpasswd` via son entrée standard, puis leurs références sont supprimées.
Ils ne figurent ni dans les arguments des commandes, ni dans les variables
d’environnement, ni dans les journaux ou le JSON de reprise. Le système installé
conserve les empreintes habituelles dans `/etc/shadow`.

L’utilisateur et root ont chacun une étape persistante. À la reprise, seuls les
mots de passe dont l’étape est incomplète sont redemandés, avant de poursuivre.
Une ancienne session qui verrouillait root demande maintenant son mot de passe
sans changer celui de l’utilisateur déjà configuré.

Une erreur de téléchargement, de dépendance ou de compilation arrête l’installation
et conserve l’état de reprise. Le bilan AUR reste dans le compte cible sous
`~/.local/state/arch-personnel/options-en-echec.json`, avec le journal de l’installateur.
Les paquets AUR déjà installés sont ignorés à la reprise grâce à `--needed`.

Références : [manuel de yay](https://github.com/Jguer/yay/blob/next/doc/yay.8),
[makepkg](https://man.archlinux.org/man/makepkg.8.en),
[chpasswd](https://man.archlinux.org/man/chpasswd.8.en),
[pacstrap](https://man.archlinux.org/man/pacstrap.8).
