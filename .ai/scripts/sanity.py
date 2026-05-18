# .ai/scripts/sanity.py
def sanity(func):
    """Marca una función para ser ejecutada como chequeo de sanidad."""
    func._sanity_check = True
    return func
