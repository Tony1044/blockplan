Put your certificate here to switch Blockplan to HTTPS. Restart Blockplan afterwards.

Any one of these works:
  cert.pem and key.pem
  fullchain.pem and privkey.pem   (as Let's Encrypt makes them)
  a .crt (or .cer) file and a .key file with the same name
  one .pfx or .p12 file           (as Windows and many IT teams export them;
                                   put its password in TLS_PFX_PASSWORD in .env)

The certificate should include any intermediate certificates from your provider.
If the key has a password, put it in TLS_KEY_PASSWORD in .env.

Until you add one, Blockplan makes a self-signed certificate here the first time it
starts (self-signed-cert.pem and self-signed-key.pem), so https:// works straight
away. Browsers warn about it until it's trusted. A certificate you add is used instead.

Files in this folder are never uploaded to GitHub.
