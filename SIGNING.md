# Signing a Speedometer release for Smart App Control

Windows Smart App Control blocks this build because its publisher cannot be
verified. This cannot be fixed by changing Python code, renaming the EXE, or
using a self-signed certificate. The released binary must be Authenticode-signed
with a valid code-signing certificate from a certificate authority in the
Microsoft Trusted Root Program, or signed through Microsoft Trusted Signing.

## Required one-time setup

1. Obtain a code-signing certificate from a trusted provider, or create a
   Microsoft Trusted Signing account associated with the publisher.
2. Import the certificate and its private key into **Current User > Personal >
   Certificates** on the signing computer. Do not add the PFX or password to
   this repository.
3. Install the Windows SDK **Signing Tools for Desktop Apps**, which supplies
   `signtool.exe`.

## Sign this release

Find the certificate thumbprint in `certmgr.msc` under Personal > Certificates;
remove any spaces. Then run:

```powershell
.\sign-release.ps1 -CertificateThumbprint YOUR_40_CHARACTER_THUMBPRINT
```

The script signs `dist\Speedometer.exe`, timestamps it, and verifies its
Authenticode signature. Do not modify the file after signing.

## Verify before distributing

```powershell
Get-AuthenticodeSignature .\dist\Speedometer.exe | Format-List Status,SignerCertificate,TimeStamperCertificate
```

The status must be `Valid` and the certificate subject must show the intended
publisher. Sign every executable and DLL included in a release.

For production distribution, use the same publisher identity for every release
and retain the signature-verification result with the release artifact.

Microsoft states that Smart App Control recognizes apps signed by certificates
from trusted providers; it also supports Microsoft Trusted Signing. See
[Microsoft's Smart App Control signing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control).
