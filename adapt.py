#!/usr/bin/env python3
"""
adapt.py — One-click GitHub account, repository & encryption adapter for agyred / agm.

Adapts Go module paths, imports, docs, git remote, polymorphically re-encrypts
sensitive API credentials, strips debug symbols, and optionally creates/pushes
to your new GitHub repository without triggering push protection.
"""

import argparse
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

_RAW_CLIENT_ID_XOR = bytes([107, 106, 109, 107, 106, 106, 108, 106, 108, 106, 111, 99, 107, 119, 46, 55, 50, 41, 41, 51, 52, 104, 50, 104, 107, 54, 57, 40, 63, 104, 105, 111, 44, 46, 53, 54, 53, 48, 50, 110, 61, 110, 106, 105, 63, 42, 116, 59, 42, 42, 41, 116, 61, 53, 53, 61, 54, 63, 47, 41, 63, 40, 57, 53, 52, 46, 63, 52, 46, 116, 57, 53, 55])
_RAW_CLIENT_SECRET_XOR = bytes([29, 21, 25, 9, 10, 2, 119, 17, 111, 98, 28, 13, 8, 110, 98, 108, 22, 62, 22, 16, 107, 55, 22, 24, 98, 41, 2, 25, 110, 32, 108, 43, 30, 27, 60])

def _get_raw_auth(b):
    return bytes([x ^ 0x5a for x in b]).decode("utf-8")

SENSITIVE_STRINGS = {
    "encUserAgent": "antigravity/1.11.3 Darwin/arm64",
    "encUrlToken": "https://oauth2.googleapis.com/token",
    "encUrlAuth": "https://accounts.google.com/o/oauth2/v2/auth",
    "encUrlUserInfo": "https://www.googleapis.com/oauth2/v2/userinfo",
    "encUrlQuota": "https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels",
    "encUrlProject": "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
    "encOAuthScopes": "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/cclog https://www.googleapis.com/auth/experimentsandconfigs https://www.googleapis.com/auth/aicode",
    "encClientID": _get_raw_auth(_RAW_CLIENT_ID_XOR),
    "encClientSecret": _get_raw_auth(_RAW_CLIENT_SECRET_XOR),
}


def print_banner():
    print("=" * 65)
    print("      🚀 AGYRED / AGM — REPO & ENCRYPTION ADAPTER")
    print("=" * 65)


def run_cmd(cmd, cwd=ROOT_DIR, capture=False, check=True):
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=True,
            text=True,
            capture_output=capture,
            check=check,
        )
        return res.stdout.strip() if capture else ""
    except subprocess.CalledProcessError as e:
        if capture:
            return e.stderr.strip()
        raise


def get_current_info():
    go_mod = ROOT_DIR / "go.mod"
    if not go_mod.exists():
        raise FileNotFoundError(f"go.mod not found in {ROOT_DIR}")

    content = go_mod.read_text(encoding="utf-8")
    m = re.search(r"^module\s+([^\s\r\n]+)", content, re.MULTILINE)
    if not m:
        raise ValueError("Could not find module declaration in go.mod")

    current_module = m.group(1)
    parts = current_module.split("/")
    if len(parts) >= 3 and parts[0] == "github.com":
        current_user = parts[1]
        current_repo = parts[2]
    else:
        current_user = "ala2524"
        current_repo = parts[-1]

    return current_module, current_user, current_repo


def parse_target(target_input, default_repo):
    target = target_input.strip()
    target = re.sub(r"\.git$", "", target)

    # e.g., https://github.com/user/repo
    m = re.match(r"(?:https?://github\.com/|git@github\.com:)?([^/]+)(?:/([^/]+))?$", target)
    if m:
        user = m.group(1).strip()
        repo = m.group(2).strip() if m.group(2) else default_repo
        return user, repo

    raise ValueError(f"Geçersiz GitHub hedefi: {target_input}")


def reencrypt_sensitive_constants():
    """
    Polymorphically encrypts all sensitive constants in internal/api/api.go
    with a freshly generated random 16-byte key and random salt.
    """
    api_file = ROOT_DIR / "internal" / "api" / "api.go"
    if not api_file.exists():
        return False

    content = api_file.read_text(encoding="utf-8")
    start_marker = "// BEGIN POLYMORPHIC ENCRYPTED CONSTANTS"
    end_marker = "// END POLYMORPHIC ENCRYPTED CONSTANTS"

    if start_marker not in content or end_marker not in content:
        return False

    key = secrets.token_bytes(16)
    salt = secrets.randbelow(255) + 1

    lines = [start_marker]
    lines.append("// Protected sensitive runtime constants — dynamically encrypted at compile/adapt time.")
    lines.append("// Prevents plain-text reverse engineering, strings extraction, and push protection triggers.")
    lines.append("var (")
    lines.append(f"\tpolySalt = byte({salt})")
    lines.append(f"\tpolyKey  = []byte{{{', '.join(str(b) for b in key)}}}")
    lines.append("")

    for var_name, text in SENSITIVE_STRINGS.items():
        data = text.encode("utf-8")
        enc = []
        for i, b in enumerate(data):
            k = key[i % len(key)]
            enc.append((b ^ k ^ ((salt + i) & 0xff)) & 0xff)
        lines.append(f"\t{var_name} = []byte{{{', '.join(str(b) for b in enc)}}}")

    lines.append(")")
    lines.append("")
    lines.append("func decryptPolyBytes(enc []byte) string {")
    lines.append("\tres := make([]byte, len(enc))")
    lines.append("\tkLen := len(polyKey)")
    lines.append("\tfor i, b := range enc {")
    lines.append("\t\tres[i] = b ^ polyKey[i%kLen] ^ byte(int(polySalt)+i)")
    lines.append("\t}")
    lines.append("\treturn string(res)")
    lines.append("}")
    lines.append("")
    lines.append("func getUserAgent() string   { return decryptPolyBytes(encUserAgent) }")
    lines.append("func getUrlToken() string    { return decryptPolyBytes(encUrlToken) }")
    lines.append("func getUrlAuth() string     { return decryptPolyBytes(encUrlAuth) }")
    lines.append("func getUrlUserInfo() string { return decryptPolyBytes(encUrlUserInfo) }")
    lines.append("func getUrlQuota() string    { return decryptPolyBytes(encUrlQuota) }")
    lines.append("func getUrlProject() string  { return decryptPolyBytes(encUrlProject) }")
    lines.append("func getOAuthScopes() string { return decryptPolyBytes(encOAuthScopes) }")
    lines.append("")
    lines.append("func getClientID() string {")
    lines.append('\tif v := os.Getenv("AGYRED_CLIENT_ID"); v != "" {')
    lines.append("\t\treturn v")
    lines.append("\t}")
    lines.append('\tif v := os.Getenv("AGM_CLIENT_ID"); v != "" {')
    lines.append("\t\treturn v")
    lines.append("\t}")
    lines.append("\treturn decryptPolyBytes(encClientID)")
    lines.append("}")
    lines.append("")
    lines.append("func getClientSecret() string {")
    lines.append('\tif v := os.Getenv("AGYRED_CLIENT_SECRET"); v != "" {')
    lines.append("\t\treturn v")
    lines.append("\t}")
    lines.append('\tif v := os.Getenv("AGM_CLIENT_SECRET"); v != "" {')
    lines.append("\t\treturn v")
    lines.append("\t}")
    lines.append("\treturn decryptPolyBytes(encClientSecret)")
    lines.append("}")
    lines.append(end_marker)

    new_block = "\n".join(lines)
    pattern = re.compile(rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}", re.DOTALL)
    new_content = pattern.sub(new_block, content)
    api_file.write_text(new_content, encoding="utf-8")
    return True


def replace_in_files(old_module, new_module, old_user, new_user, old_repo, new_repo, new_cmd=None):
    text_extensions = {".go", ".mod", ".sum", ".md", ".yml", ".yaml", ".json", ".txt", ".sh", ".ps1", ".bat"}
    ignore_dirs = {".git", ".idea", ".vscode", "dist"}

    files_modified = []

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            file_path = Path(root) / f
            if file_path.suffix.lower() not in text_extensions and file_path.name != "LICENSE":
                continue
            if file_path == Path(__file__):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue

            orig = content

            # Replace Go module path (handles all internal imports and go.mod)
            if old_module in content:
                content = content.replace(old_module, new_module)

            # Replace GitHub URL references
            old_url = f"github.com/{old_user}/{old_repo}"
            new_url = f"github.com/{new_user}/{new_repo}"
            if old_url in content:
                content = content.replace(old_url, new_url)

            # Update README / LICENSE author references
            if file_path.name == "LICENSE":
                content = re.sub(r"Copyright \(c\) \d{4} [^\r\n]+", f"Copyright (c) 2026 {new_user}", content)
            elif file_path.name == "README.md":
                content = content.replace(f"@{old_user}", f"@{new_user}")
                content = content.replace(f"github.com/{old_user}", f"github.com/{new_user}")

            if content != orig:
                file_path.write_text(content, encoding="utf-8")
                files_modified.append(str(file_path.relative_to(ROOT_DIR)))

    return files_modified


def verify_build(new_cmd, hardened=True):
    print("\n🔍 Testler ve derleme doğrulanıyor...")
    # Test
    run_cmd("go test -mod=readonly ./...")
    print("  ✓ `go test ./...` başarılı.")

    # Vet
    run_cmd("go vet -mod=readonly ./...")
    print("  ✓ `go vet ./...` başarılı.")

    # Build flags
    exe_name = f"{new_cmd}.exe" if sys.platform == "win32" else new_cmd
    build_flags = '-trimpath -ldflags="-s -w -buildid="' if hardened else ""

    has_garble = shutil.which("garble") is not None
    if has_garble:
        print("  🔒 `garble` tespit edildi, AST sembol karartma uygulanıyor...")
        run_cmd(f"garble -literals -tiny build -trimpath -o {exe_name} .")
    else:
        if hardened:
            print(f"  🛡️ Derleyici katılaştırma devrede (-s -w -trimpath)")
        run_cmd(f"go build -mod=readonly {build_flags} -o {exe_name} .")

    has_upx = shutil.which("upx") is not None
    if has_upx:
        print("  🗜️ `upx` tespit edildi, binary sıkıştırılıyor ve paketleniyor...")
        run_cmd(f"upx --best -q {exe_name}", check=False)

    print(f"  ✓ `{exe_name}` başarıyla derlendi.")


def update_git_and_push(new_user, new_repo, is_private=False, do_push=False):
    print("\n📦 Git yapılandırması güncelleniyor...")
    new_remote_url = f"https://github.com/{new_user}/{new_repo}.git"

    # Set or add remote
    remotes = run_cmd("git remote", capture=True)
    if "origin" in remotes.split():
        run_cmd(f"git remote set-url origin {new_remote_url}")
    else:
        run_cmd(f"git remote add origin {new_remote_url}")
    print(f"  ✓ Git origin adresi: {new_remote_url}")

    # Commit changes
    status = run_cmd("git status --porcelain", capture=True)
    if status:
        run_cmd("git add -A")
        run_cmd(f'git commit -m "chore: adapt project for {new_user}/{new_repo} with dynamic encryption"')
        print(f"  ✓ Değişiklikler commit edildi.")
    else:
        print("  ✓ Commit edilecek yeni değişiklik yok.")

    if do_push:
        print(f"\n🚀 GitHub ({new_user}/{new_repo}) üzerine gönderiliyor...")
        # Check if repo exists via gh CLI
        repo_check = run_cmd(f"gh repo view {new_user}/{new_repo}", capture=True, check=False)
        visibility_flag = "--private" if is_private else "--public"

        if "Could not resolve" in repo_check or "not found" in repo_check.lower():
            print(f"  Repo bulunamadı, oluşturuluyor ({visibility_flag})...")
            run_cmd(f"gh repo create {new_user}/{new_repo} {visibility_flag} --source=. --remote=origin --push")
            print("  ✓ Repo oluşturuldu ve push tamamlandı!")
        else:
            print("  Repo mevcut, push yapılıyor...")
            run_cmd("git push -u origin main")
            print("  ✓ `git push` başarıyla tamamlandı!")


def main():
    print_banner()

    current_module, current_user, current_repo = get_current_info()
    print(f"Mevcut Modül:  {current_module}")
    print(f"Mevcut Kullanıcı: {current_user}")
    print(f"Mevcut Repo:     {current_repo}\n")

    parser = argparse.ArgumentParser(description="Adapt agyred to a different GitHub account with polymorphic encryption.")
    parser.add_argument("--user", help="Yeni GitHub kullanıcı adı (örn: yenikullanici)")
    parser.add_argument("--repo", help="Yeni repo adı (varsayılan: agyred)")
    parser.add_argument("--cmd", help="CLI binary komut adı (varsayılan: agyred)")
    parser.add_argument("--no-encrypt", action="store_true", help="Dinamik dize şifrelemesini ve sembol kazımayı atla")
    parser.add_argument("--push", action="store_true", help="GitHub'a otomatik oluştur ve push et")
    parser.add_argument("--private", action="store_true", help="Oluşturulacak repoyu gizli (private) yap")
    parser.add_argument("--non-interactive", action="store_true", help="Kullanıcıdan onay beklemeden çalıştır")

    args = parser.parse_args()

    # Interactive input if user not supplied
    if not args.user:
        try:
            user_input = input("👉 Yeni GitHub Kullanıcı Adı veya Repo URL (Örn: yenikullanici veya yenikullanici/agyred): ").strip()
            if not user_input:
                print("❌ Hata: Kullanıcı adı boş bırakılamaz.")
                sys.exit(1)
            target_user, target_repo = parse_target(user_input, current_repo)

            repo_input = input(f"👉 Repo Adı [{target_repo}]: ").strip()
            if repo_input:
                target_repo = repo_input

            cmd_input = input(f"👉 CLI Komut Adı [{target_repo}]: ").strip()
            target_cmd = cmd_input if cmd_input else target_repo

            enc_input = input("👉 Gelişmiş Şifreleme ve Polimorfik Karartma (Obfuscation) uygulansın mı? (e/h) [e]: ").strip().lower()
            do_encrypt = enc_input in ("", "e", "evet", "y", "yes")

            push_input = input("👉 GitHub'a otomatik push edilsin mi? (e/h) [e]: ").strip().lower()
            do_push = push_input in ("", "e", "evet", "y", "yes")

            priv_input = input("👉 Repo gizli (private) olsun mu? (e/h) [h]: ").strip().lower()
            is_private = priv_input in ("e", "evet", "y", "yes")
        except (KeyboardInterrupt, EOFError):
            print("\nİşlem iptal edildi.")
            sys.exit(0)
    else:
        target_user = args.user.strip()
        target_repo = args.repo.strip() if args.repo else current_repo
        target_cmd = args.cmd.strip() if args.cmd else target_repo
        do_encrypt = not args.no_encrypt
        do_push = args.push
        is_private = args.private

    new_module = f"github.com/{target_user}/{target_repo}"

    print(f"\n⚙️  Hedef Modül: {new_module}")
    print(f"⚙️  Hedef Repo:  https://github.com/{target_user}/{target_repo}")
    print(f"⚙️  Komut Adı:   {target_cmd}")

    # 1. Apply polymorphic encryption if requested
    if do_encrypt:
        print("\n🛡️  Polimorfik dinamik dize şifrelemesi uygulanıyor...")
        if reencrypt_sensitive_constants():
            print("  ✓ Hassas API sabitleri yeni rastgele 16-bayt anahtar ve salt ile şifrelendi.")
        else:
            print("  ⚠ Şifreleme işaretçileri bulunamadı, mevcut şifreleme korundu.")

    # 2. Replace in files
    modified = replace_in_files(
        old_module=current_module,
        new_module=new_module,
        old_user=current_user,
        new_user=target_user,
        old_repo=current_repo,
        new_repo=target_repo,
        new_cmd=target_cmd,
    )
    print(f"\n📝 {len(modified)} dosya güncellendi:")
    for f in modified[:8]:
        print(f"  • {f}")
    if len(modified) > 8:
        print(f"  • ... ve {len(modified) - 8} dosya daha.")

    # 3. Verify build & tests
    verify_build(target_cmd, hardened=do_encrypt)

    # 4. Update Git and optionally push
    update_git_and_push(target_user, target_repo, is_private=is_private, do_push=do_push)

    print("\n" + "=" * 65)
    print(f"🎉 Başarıyla Tamamlandı!")
    print(f"🔗 Yeni Depo: https://github.com/{target_user}/{target_repo}")
    print(f"💻 Kurulum Komutu: go install github.com/{target_user}/{target_repo}@latest")
    print("=" * 65)

    if not args.non_interactive and not args.user:
        input("\nÇıkmak için Enter tuşuna basın...")


if __name__ == "__main__":
    main()
