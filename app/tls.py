"""HTTPS: finds a certificate, or makes a self-signed one, and checks it before Blockplan starts.

The simplest way to switch HTTPS on is to put the certificate in the certs folder:
  - cert.pem and key.pem, or
  - fullchain.pem and privkey.pem (as Let's Encrypt makes them), or
  - a .crt and a .key file, or
  - one .pfx or .p12 file (as Windows and many IT teams export them), with TLS_PFX_PASSWORD if it has one.
"""
import datetime as dt
import ipaddress
import os
import socket
import ssl
from dataclasses import dataclass
from pathlib import Path

from . import config


class TLSError(Exception):
    pass


@dataclass
class TLS:
    certfile: str
    keyfile: str
    password: str | None
    source: str
    expires: dt.datetime | None
    names: list
    self_signed: bool


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(config.BASE_DIR))
    except ValueError:
        return str(p)


def _find_files():
    """Explicit settings first, then anything recognisable in the certs folder."""
    if config.TLS_CERT or config.TLS_KEY:
        if not (config.TLS_CERT and config.TLS_KEY):
            raise TLSError("Set both TLS_CERT and TLS_KEY in .env, or neither.")
        return ("pem", Path(config.TLS_CERT), Path(config.TLS_KEY))
    if config.TLS_PFX:
        return ("pfx", Path(config.TLS_PFX), None)
    d = config.CERT_DIR
    if not d.is_dir():
        return None
    for cert, key in (("cert.pem", "key.pem"), ("fullchain.pem", "privkey.pem"), ("certificate.pem", "private.pem")):
        if (d / cert).is_file() and (d / key).is_file():
            return ("pem", d / cert, d / key)
    crts = sorted(p for p in d.iterdir() if p.suffix.lower() in (".crt", ".cer"))
    keys = sorted(p for p in d.iterdir() if p.suffix.lower() == ".key")
    if crts and keys:
        same = [(c, k) for c in crts for k in keys if c.stem == k.stem]
        c, k = same[0] if same else (crts[0], keys[0])
        return ("pem", c, k)
    pfx = sorted(p for p in d.iterdir() if p.suffix.lower() in (".pfx", ".p12"))
    if pfx:
        return ("pfx", pfx[0], None)
    if (d / "self-signed-cert.pem").is_file() and (d / "self-signed-key.pem").is_file():
        return ("pem", d / "self-signed-cert.pem", d / "self-signed-key.pem")
    return None


def _from_pfx(path: Path) -> tuple[Path, Path]:
    """Unpack a .pfx into PEM files Blockplan can use. The unpacked key is kept private to this user."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    if not path.is_file():
        raise TLSError(f"Can't find the certificate file {_rel(path)}.")
    pw = config.TLS_PFX_PASSWORD.encode() if config.TLS_PFX_PASSWORD else None
    try:
        key, cert, extra = pkcs12.load_key_and_certificates(path.read_bytes(), pw)
    except ValueError:
        raise TLSError(f"Couldn't open {_rel(path)}. If it has a password, put it in TLS_PFX_PASSWORD in .env.")
    if not key or not cert:
        raise TLSError(f"{_rel(path)} doesn't contain both a certificate and its private key. Export it again with the private key included.")
    out = config.DATA_DIR / "tls"
    out.mkdir(parents=True, exist_ok=True)
    certfile, keyfile = out / "from-pfx-cert.pem", out / "from-pfx-key.pem"
    chain = cert.public_bytes(serialization.Encoding.PEM) + b"".join(c.public_bytes(serialization.Encoding.PEM) for c in (extra or []))
    certfile.write_bytes(chain)
    fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return certfile, keyfile


def make_self_signed() -> tuple[Path, Path]:
    """A certificate for testing. Browsers will warn about it until it's trusted on that computer."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    d = config.CERT_DIR
    d.mkdir(parents=True, exist_ok=True)
    certfile, keyfile = d / "self-signed-cert.pem", d / "self-signed-key.pem"
    host = socket.gethostname() or "localhost"
    names = ["localhost", host] + [h for h in config.HTTPS_HOSTNAMES if h]
    alt, seen = [], set()
    for n in names + ["127.0.0.1", "::1"]:
        if n.lower() in seen:
            continue
        seen.add(n.lower())
        try:
            alt.append(x509.IPAddress(ipaddress.ip_address(n)))
        except ValueError:
            alt.append(x509.DNSName(n))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Blockplan (self-signed)")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(minutes=5))
            .not_valid_after(now + dt.timedelta(days=397))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    fd = os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return certfile, keyfile


def _describe(certfile: Path):
    from cryptography import x509
    try:
        first = certfile.read_bytes()
        cert = x509.load_pem_x509_certificates(first)[0]
    except (ValueError, IndexError):
        try:
            cert = x509.load_der_x509_certificate(certfile.read_bytes())
        except ValueError:
            raise TLSError(f"{_rel(certfile)} isn't a certificate Blockplan can read. Use a PEM (.pem or .crt) or .pfx file.")
    try:
        alt = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        names = [str(n.value) for n in alt]
    except x509.ExtensionNotFound:
        names = [a.value for a in cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)]
    self_signed = cert.issuer == cert.subject
    return cert.not_valid_after_utc, names, self_signed


def setup() -> TLS | None:
    """Returns how to serve HTTPS, or None for plain HTTP. Raises TLSError with a plain explanation."""
    mode = config.HTTPS
    if mode == "off":
        return None
    found = _find_files()
    if mode == "self-signed" and found and found[1].name == "self-signed-cert.pem":
        try:
            expires, _, _ = _describe(found[1])
            if expires < dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7):
                found = None  # about to expire: make a fresh one
        except TLSError:
            found = None
    if not found and mode == "self-signed":
        c, k = make_self_signed()
        found = ("pem", c, k)
    if not found:
        if mode == "on":
            raise TLSError(f"HTTPS=on, but there's no certificate in {_rel(config.CERT_DIR)}. Put cert.pem and key.pem (or a .pfx file) there, or set HTTPS=self-signed to make one for testing.")
        return None
    kind, a, b = found
    if kind == "pfx":
        source = _rel(a)
        certfile, keyfile = _from_pfx(a)
        password = None
    else:
        certfile, keyfile, source, password = a, b, _rel(a), (config.TLS_KEY_PASSWORD or None)
        for p in (certfile, keyfile):
            if not p.is_file():
                raise TLSError(f"Can't find {_rel(p)}.")
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(certfile), str(keyfile), password=password)
    except ssl.SSLError as e:
        msg = str(e).lower()
        if "key values mismatch" in msg:
            raise TLSError(f"The private key doesn't match the certificate in {source}. Check you have the right pair of files.")
        if "bad decrypt" in msg or "password" in msg:
            raise TLSError("The private key has a password. Put it in TLS_KEY_PASSWORD in .env.")
        raise TLSError(f"The certificate or key in {source} couldn't be used ({e.reason or e}). Use PEM files or a .pfx file.")
    expires, names, self_signed = _describe(Path(certfile))
    return TLS(str(certfile), str(keyfile), password, source, expires, names, self_signed)


def explain(t: TLS) -> list[str]:
    """Lines for the console when Blockplan starts."""
    lines = [f"HTTPS is on, using {t.source}."]
    now = dt.datetime.now(dt.timezone.utc)
    if t.expires:
        when = t.expires.strftime("%-d %B %Y") if os.name != "nt" else t.expires.strftime("%d %B %Y").lstrip("0")
        if t.expires < now:
            lines.append(f"Warning: this certificate expired on {when}. Browsers will refuse it until you replace it.")
        elif t.expires - now < dt.timedelta(days=30):
            lines.append(f"Warning: this certificate expires on {when}. Replace it soon.")
        else:
            lines.append(f"It's valid until {when}.")
    if t.names:
        lines.append("It covers: " + ", ".join(t.names[:8]) + ("…" if len(t.names) > 8 else ""))
    if t.self_signed:
        lines.append("It's self-signed, so browsers show a warning. Choose Advanced, then Continue or Proceed, to open Blockplan.")
        lines.append("To stop the warning, trust the certificate on each computer, or put a real certificate in the certs folder. See the README.")
    return lines
