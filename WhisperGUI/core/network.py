"""Use a bundled public CA trust store, including in frozen distributions."""
import ssl
import certifi


def ssl_context():
    return ssl.create_default_context(cafile=certifi.where())
