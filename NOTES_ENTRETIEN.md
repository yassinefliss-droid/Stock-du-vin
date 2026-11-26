# Notes d'entretien — Stock en cave (1 page)

## Choix techniques et justification
- **FastAPI + SQLAlchemy 2 + Pydantic v2** : API typée, validation et doc OpenAPI gratuites. **Alembic** pour des migrations reproductibles ; PostgreSQL en prod (verrou de ligne sur les sorties), SQLite pour des tests rapides (~7 s).
- **Stock calculé, jamais stocké** : stock = Σ des mouvements signés. Pas de désynchronisation possible, historique auditable ; coût : une jointure agrégée (négligeable à cette échelle). Règle « jamais négatif » centralisée dans `services/stock.py`.
- **Assistant par tool calling, pas de SQL libre** : le LLM *choisit* parmi 5 fonctions en lecture seule ; les chiffres viennent de Python. Fiable, sûr, vérifiable (outil + arguments affichés).
- **Un seul socle d'outils, deux modes** (LLM ou règles) : l'appli marche sans clé, et l'évaluation compare les deux sur les mêmes fonctions. Repli automatique en mode règles si le LLM échoue.
- **Front Jinja2 sans JS** : suffisant pour un outil interne, zéro build, facile à relire. Les routes web réutilisent les mêmes services que l'API.
- **JWT** (Bearer ou cookie HttpOnly) + rôles via une dépendance `require_roles`. Mots de passe hachés avec bcrypt.
- **Évaluation chiffrée** : réponses attendues calculées indépendamment des outils (boucles Python sur le seed), base ancrée à une date fixe.

## Difficultés rencontrées
- **Recherche de produit en français** : « Saint-Émilion » vs « saint emilion ». Solution : colonne `search_text` normalisée (sans accents/tirets), indépendante de la base (pas d'extension `unaccent`).
- **Dates relatives** (« la semaine dernière ») : le LLM ne doit pas les deviner. Période nommée résolue côté Python (lundi→dimanche), date du jour injectée dans le prompt et figeable pour les tests/l'éval.
- **Mode règles** : repérer le produit cité sans liste codée en dur → plus longue suite de mots de la question présente dans le texte d'un produit. L'éval a révélé un bug réel : « prix de **vente** » déclenchait la règle « ventes » ; corrigé + test de non-régression.
- **Honnêteté de l'éval** : mon premier « 100 % Groq » était en fait du mode règles (modèle par défaut retiré par Groq, repli silencieux) → l'éval affiche maintenant le mode réel par réponse. Ensuite : limite de débit (retry sur 429), modèle qui écrit « Rouge » au lieu de « rouge » (schéma d'outil précisé), liste sans nombre (prompt ajusté). Résultat final Groq `gpt-oss-120b` 15/15, mais prompt ajusté sur ce même jeu de 15 questions, une seule exécution : optimiste. Anthropic non mesuré.
- Docker absent de ma machine de dev : migration → seed → API → web validés d'abord sur un PostgreSQL local, puis `docker compose up` confirmé ensuite sur la machine de l'auteur.

## 8 questions probables
1. **Pourquoi pas du text-to-SQL ?** Risque d'erreurs silencieuses (mauvaise règle de stock), d'injection/écriture, résultats non reproductibles. Les outils encapsulent la logique métier, testée une fois ; le modèle ne fait que router et rédiger.
2. **Comment éviter que le LLM invente un chiffre ?** Prompt strict, réponse construite à partir du JSON d'outil, hors périmètre → pas d'outil. Amélioration prévue : vérifier automatiquement que chaque nombre de la réponse figure dans le résultat d'outil.
3. **Comment garantir un stock jamais négatif, même en concurrence ?** Vérification dans le service avant insertion + `SELECT … FOR UPDATE` sur la ligne produit (PostgreSQL) : deux sorties simultanées sont sérialisées. Limite connue : pas de contrôle à la date pour un mouvement antidaté.
4. **Pourquoi calculer le stock plutôt que le stocker ?** Source unique de vérité (les mouvements), pas de dérive. Si les volumes explosent : table de snapshots ou colonne dénormalisée mise à jour dans la même transaction.
5. **Comment as-tu évalué l'assistant et que valent les résultats ?** 15 questions, attendus calculés indépendamment du code testé, 2 métriques (bon outil, réponse correcte). Règles et Groq : 15/15, mais optimistes (petit jeu, prompt/règles ajustés sur ce jeu, une exécution). Un repli silencieux en mode règles m'a d'abord fait croire à tort que Groq marchait : l'éval affiche désormais le mode réel.
6. **Comment sont gérés les rôles ?** Dépendance FastAPI `require_roles` (lecture seule → 403 sur toute écriture, seul admin gère les utilisateurs), mêmes contrôles côté web, testés par rôle.
7. **Quelles sont les failles de sécurité restantes ?** Pas de CSRF dédié (SameSite=Lax seulement), pas de rate-limit au login, secrets de démo à changer. Les requêtes sont paramétrées (SQLAlchemy) et l'assistant est en lecture seule.
8. **Comment passerais-tu à l'échelle / en production ?** Pagination, index sur (produit, date) déjà en place pour l'historique, workers uvicorn/gunicorn, secrets via variables d'environnement, CI qui déploie, journalisation des appels d'outils, évaluation LLM en continu avec un jeu de questions élargi.
