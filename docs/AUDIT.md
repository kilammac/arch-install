# Audit de la copie destinée à GitHub

## Résultat sur les fichiers présents

La recherche de signatures et l’examen des correspondances n’ont pas détecté de
clé privée, jeton GitHub/OpenAI/AWS, mot de passe de compte ou URL avec identifiants.
Aucun profil navigateur, trousseau, historique Fish, clé SSH ou fichier de session
n’est présent dans le paquet de configuration.

Les images examinées sont des fonds Arch et des illustrations d’interface ; les
fichiers image inspectés ne contiennent pas de champs EXIF. Les droits de
redistribution des illustrations restent à vérifier avant diffusion publique.

## Données retirées dans cette copie seulement

- Inventaire détaillé de paquets et informations sur la machine source.
- Chemins absolus, nom de compte suggéré et versions des paquets de la source
  dans le catalogue ; choix de logiciels conservés pour l’installation.
- Lieu et coordonnées par défaut de météo/prières : remplacés par « À configurer ».
- Constante de jeton Fast.com dans les deux helpers de débit : externalisée.
  Ce jeton servait à l’API du service ; il n’a pas été identifié comme un secret
  de compte personnel. Son externalisation évite de publier un jeton en dur.
- Dossier `.git` exclu de la copie vers `/opt/arch-personnel` pendant l’installation.

Pour le débit Fast.com, configurer localement `QS_FAST_TOKEN`, ou le fichier
`~/.config/quickshell/fast-token` contenant uniquement la valeur. Le `.gitignore`
exclut ce fichier. Sans valeur, ce test affiche une demande de configuration ;
les autres fonctions du bureau restent disponibles.

L’original personnel reste inchangé. Cette copie utilise des valeurs génériques ;
tu peux choisir ton compte et ton fuseau dans l’installateur et régler le lieu
depuis le panneau après le premier démarrage. Les fonctions prières et cassette
sont conservées. Publier cette configuration révèle néanmoins tes préférences
logicielles et les fonctions de ton bureau.

## Contrôles futurs

```bash
python -B audit_publication.py
bash install.sh --check
python -B -m unittest -v test_hardware test_installer test_tui test_session_state test_snapshots test_options_permissions test_package_exclusions
```

Le scanner local est un contrôle par motifs, pas une preuve d’absence de tout
secret ; il ne remplace pas une revue avant ajout de nouveaux fichiers. Les
outils spécialisés Gitleaks/TruffleHog ne sont pas installés dans l’environnement
d’audit. Aucune authentification ou validité de jeton n’a été testée sur un service.

La protection GitHub peut aider, mais ne détecte pas toutes les valeurs ni toutes
les données personnelles : [documentation GitHub](https://docs.github.com/en/code-security/reference/secret-security/secret-scanning-scope).

Les nouveaux fichiers de reprise restent sous `/run` ou dans le sous-volume
`@installstate` de la cible ; une copie externe n’est autorisée qu’hors du dépôt.
Leur contenu n’inclut pas les mots de passe et n’est jamais envoyé à GitHub.
