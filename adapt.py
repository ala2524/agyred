#!/usr/bin/env python3
"""
adapt.py — One-click GitHub account & repository adapter for agyred / agm.

Adapts Go module paths, imports, docs, git remote, and optionally creates
and pushes to your new GitHub repository without triggering push protection.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


def print_banner():
    print("=" * 65)
    print("      🚀 AGYRED / AGM — REPO & GITHUB ADAPTER")
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


def verify_build(new_cmd):
    print("\n🔍 Testler ve derleme doğrulanıyor...")
    # Test
    run_cmd("go test -mod=readonly ./...")
    print("  ✓ `go test ./...` başarılı.")

    # Vet
    run_cmd("go vet -mod=readonly ./...")
    print("  ✓ `go vet ./...` başarılı.")

    # Build
    exe_name = f"{new_cmd}.exe" if sys.platform == "win32" else new_cmd
    run_cmd(f"go build -mod=readonly -o {exe_name} .")
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
        run_cmd(f'git commit -m "chore: adapt project for {new_user}/{new_repo}"')
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

    parser = argparse.ArgumentParser(description="Adapt agyred to a different GitHub account.")
    parser.add_argument("--user", help="Yeni GitHub kullanıcı adı (örn: yenikullanici)")
    parser.add_argument("--repo", help="Yeni repo adı (varsayılan: agyred)")
    parser.add_argument("--cmd", help="CLI binary komut adı (varsayılan: agyred)")
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
        do_push = args.push
        is_private = args.private

    new_module = f"github.com/{target_user}/{target_repo}"

    print(f"\n⚙️  Hedef Modül: {new_module}")
    print(f"⚙️  Hedef Repo:  https://github.com/{target_user}/{target_repo}")
    print(f"⚙️  Komut Adı:   {target_cmd}")

    # 1. Replace in files
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

    # 2. Verify build & tests
    verify_build(target_cmd)

    # 3. Update Git and optionally push
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
