class ErreurMetier(Exception):
    """Base des erreurs métier ; l'API les convertit en réponses HTTP."""

    status_code = 400


class Introuvable(ErreurMetier):
    status_code = 404


class StockInsuffisant(ErreurMetier):
    status_code = 409


class ConflitMetier(ErreurMetier):
    status_code = 409
