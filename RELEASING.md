# Releasing

donelogger is published to [PyPI](https://pypi.org/project/donelogger/)
automatically by GitHub Actions using **PyPI Trusted Publishing** (OIDC) — no
API token is stored anywhere. Publishing a GitHub Release builds the package and
uploads it. The workflow lives at
[.github/workflows/publish.yml](.github/workflows/publish.yml).

## Per-release steps

1. **Bump the version** in [pyproject.toml](pyproject.toml):

   ```toml
   version = "0.1.9"
   ```

   Follow [semantic versioning](https://semver.org/): patch for fixes, minor for
   backwards-compatible features, major for breaking changes.

2. **Commit and push** to `main`:

   ```bash
   git commit -am "Release 0.1.9"
   git push origin main
   ```

3. **Create a GitHub Release** with a tag that matches the version:

   - GitHub → **Releases** → **Draft a new release**
   - Tag: `v0.1.9` (create it on publish)
   - Write short release notes, then **Publish release**.

   Or from the CLI:

   ```bash
   gh release create v0.1.9 --generate-notes
   ```

4. **Watch it publish.** The **Actions** tab shows the *Publish to PyPI* run.
   When it goes green, the new version is live at
   <https://pypi.org/project/donelogger/> (usually within a minute or two).

That's it — no `twine`, no token, no manual upload.

## Gotchas

- **Bump the version first.** PyPI refuses to accept a version that already
  exists, so a forgotten bump makes the Actions run fail (red). Bump, then
  release.
- **Tag = version.** Keep the release tag (`v0.1.9`) in sync with
  `pyproject.toml` (`0.1.9`) so the published artifact matches the tag.
- **README images must use absolute URLs.** PyPI renders the README standalone,
  so relative paths like `assets/demo.gif` break there. Use the full
  `https://raw.githubusercontent.com/rkskmt/donelogger/main/...` form.

## One-time setup (already done)

The PyPI Trusted Publisher was configured once at
`https://pypi.org/manage/project/donelogger/settings/publishing/`:

| Field           | Value        |
|-----------------|--------------|
| Owner           | `rkskmt`     |
| Repository name | `donelogger` |
| Workflow name   | `publish.yml`|
| Environment     | *(blank)*    |

You only need to redo this if the repository is renamed/moved or the workflow
file is renamed.
