---
description: Build the AppImage and create a GitHub release
---

// turbo-all

1. Run the build script to generate the latest AppImage:
```bash
bash build_appimage.sh
```

2. Add changes, commit, and push to the repository:
```bash
git add .
git commit -m "Update installer and documentation"
git push
```

3. List recent releases to determine the next version number:
```bash
gh release list
```

4. Create the GitHub release and upload the AppImage:
```bash
gh release create [VERSION] ./Photoshop_Installer_x86_64.AppImage --title "[VERSION] - [TITLE]" --notes "[RELEASE_NOTES]"
```
