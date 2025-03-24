import threading

# Thread-safe set to store revoked tokens
revoked_tokens = set()
lock = threading.Lock()

def add_token_to_blocklist(token):
    """ Add a JWT token to the blocklist """
    with lock:
        revoked_tokens.add(token)

def is_token_revoked(token):
    """ Check if a JWT token is revoked """
    with lock:
        return token in revoked_tokens