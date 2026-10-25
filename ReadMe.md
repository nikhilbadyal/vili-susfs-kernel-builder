> **Xiaomi 11T Pro (vili):** `.github/workflows/build-vili.yml` builds current KernelSU-Next (real version 33314, API 5) plus SUSFS 2.3.0 on the newer published source and the working device configuration. The initial combined artifact bootlooped; a subsequent diagnostic baseline booted but exposed a Wi-Fi HAL startup mismatch. The current candidate includes the `/dev/wlan` fix and is pending compile/device verification. See [integration details](patches/README.md) and [device test history](docs/VILI_BASELINE.md).

# Shipping the Docker kernel build system as a standalone GitHub repo

This document explains how the Docker build works and how to publish it as its own repo (without kernel source, firmware, or build outputs).

---

## Exported layout (standalone repo)

What you ship in the GitHub repo:

```
.
├── Dockerfile          # Ubuntu 24.04 + LLVM 18 + aarch64 toolchain (no source inside image)
├── .dockerignore       # * (empty context; source is mounted at run time)
├── build.sh            # Host orchestrator: image, branch switch, docker run, zip
├── docker-build.sh     # Runs inside container: defconfig + make O=/out
├── clone-kernel.sh     # Clones https://github.com/NOXCIS/kernel_xiaomi_odin into ./kernel_xiaomi_odin
├── README.md
├── .gitignore          # kernel_xiaomi_odin/, out/, AnyKernel/Image, AnyKernel/dtbo.img, etc.
├── STANDALONE_REPO.md  # This file
└── AnyKernel/          # Shipped with build system; Image + dtbo.img ignored (filled by build)
    ├── anykernel.sh
    ├── LICENSE
    ├── META-INF/...    # update-binary, updater-script
    ├── test_banner.sh
    └── tools/          # busybox, magiskboot, etc. (required for flashing)
```

**Not in the repo (or in .gitignore):** `kernel_xiaomi_odin/`, `out/`, `logs/`, `AnyKernel/Image`, `AnyKernel/dtbo.img`, firmware, toolchains.

---

## How it behaves (end-to-end)

### First-time user

1. **Clone the build-system repo** (this repo). AnyKernel is already included.
2. **Get kernel source** (one of):
   - `./clone-kernel.sh` → clones [NOXCIS/kernel_xiaomi_odin](https://github.com/NOXCIS/kernel_xiaomi_odin) into `./kernel_xiaomi_odin`
   - Or: `./clone-kernel.sh <other-repo-url>` / `KERNEL_SRC=/path/to/kernel ./build.sh`
3. **Build:** `./build.sh` or `./build.sh sukisu-4.1.1` (see branches below). First build will put `Image` (and `dtbo.img` if present) into `AnyKernel/`.

### Build branches

| Invocation            | Branch         | Zip name pattern                    |
|-----------------------|----------------|-------------------------------------|
| `./build.sh`          | ksu-next-susfs | `Odin_5.4.302_KSU_NXT_SUSFS_<tag>_<date>.zip` |
| `./build.sh susfs`    | ksu-next-susfs | same                                |
| `./build.sh sukisu-4.1.1` | sukisu-4.1.1 | `Odin_5.4.302_SukiSU_4.1.1_<date>.zip` |
| `./build.sh sukisu`   | sukisu-4.1.1   | same                                |

`build.sh` switches `kernel_xiaomi_odin` to the chosen branch (and for `ksu-next-susfs`, KernelSU-Next to `dev_susfs`) before building. The packed zip’s recovery banner shows the built kernel version and build label.

### What happens when you run `./build.sh`

1. **Preflight:** Docker present and running; `KERNEL_SRC` (default `./kernel_xiaomi_odin`) exists; `docker-build.sh` exists.
2. **Image:** Build Docker image `odin-kernel-builder:arm64` once (cached).
3. **Branch:** Checkout `kernel_xiaomi_odin` to the chosen branch; for `ksu-next-susfs`, also checkout KernelSU-Next to `dev_susfs`.
4. **KSU version:** For `ksu-next-susfs` only, resolve tag for zip name (e.g. `v3.0.1`); optional `KSU_GIT_VERSION` alignment.
5. **Clean:** Remove leftover build artifacts from kernel source tree (no `make clean` in-tree).
6. **Volume:** Ensure Docker volume `odin-kernel-out` exists.
7. **Docker run:**  
   - Mount `KERNEL_SRC` → `/src` (read-only), volume → `/out`, `docker-build.sh` → `/docker-build.sh`.  
   - Run `/docker-build.sh build`: defconfig if missing, then `make -C /src O=/out -j$(nproc)`.
8. **Extract:** Copy `Image` (and `dtbo.img` if present) from volume into `AnyKernel/`.
9. **Package:** Zip `AnyKernel/` → `out/<zipname>.zip`.

### If kernel already cloned

- Run `./clone-kernel.sh` again → does **not** re-clone; runs `git fetch` and `git pull --rebase` in `kernel_xiaomi_odin`.

### Overrides

- `KERNEL_SRC=/path ./build.sh` — use kernel tree at `/path`.
- `ANYKERNEL_DIR=/path ./build.sh` — use AnyKernel at `/path`.
- `./clone-kernel.sh https://github.com/other/fork.git` — clone a different repo into `./kernel_xiaomi_odin`.

---

## How the Docker build system works (reference)

### 1. **Dockerfile** (image only)

- **Base:** `ubuntu:24.04`
- **Role:** Installs a fixed, reproducible toolchain:
  - **LLVM/Clang 18** (with versionless symlinks: `clang`, `ld.lld`, `llvm-ar`, etc.) for `LLVM=1` builds
  - **aarch64 cross-compiler** (`gcc-aarch64-linux-gnu`) for Kbuild
  - Build tools: `make`, `bc`, `bison`, `flex`, `kmod`, `dwarves`, `device-tree-compiler`, etc.
- **No `COPY`:** The image does not bundle kernel source. The Dockerfile is sent via stdin (`docker build -f - - < Dockerfile`), and `.dockerignore` excludes everything, so build context is empty. That’s intentional.
- **Env:** Sets `ARCH=arm64`, `CROSS_COMPILE=aarch64-linux-gnu-`, `LLVM=1`, `LLVM_IAS=1`, `WORKDIR /src`.

### 2. **build.sh** (host orchestrator)

- **Preflight:** Checks Docker, kernel tree at `kernel_xiaomi_odin`, and `docker-build.sh`.
- **Docker image:** Builds `odin-kernel-builder:arm64` once (cached).
- **Volumes:** Uses a named volume `odin-kernel-out` for build output (so `make O=/out` doesn’t touch the host).
- **Mounts at run time:**
  - `kernel_xiaomi_odin` → `/src` (read-only)
  - `odin-kernel-out` → `/out`
  - `docker-build.sh` → `/docker-build.sh` (read-only)
- **Flow:** Switch KernelSU branch → resolve KSU version → clean source artifacts → `docker run ... /docker-build.sh build` → copy `Image` (and optionally `dtbo.img`) from volume into AnyKernel → zip → `out/*.zip`.

### 3. **docker-build.sh** (runs inside container)

- **Input:** Kernel source at `/src` (mounted read-only), output dir `/out`.
- **Actions:** `build` (defconfig if needed, then `make -C /src O=/out -j$(nproc)`), `rebuild`, `clean`, `defconfig`, `menuconfig`.
- **Output:** `Image` at `/out/arch/arm64/boot/Image` (and DTBOs if present). Host’s `build.sh` then copies these into AnyKernel and packages the zip.

### Data flow (short)

```
Host                          Container
────                          ─────────
kernel_xiaomi_odin/  -v ro -> /src   (read-only)
docker-build.sh      -v ro -> /docker-build.sh
(named volume)       -v rw -> /out   (build output)

./build.sh  →  docker run ... /docker-build.sh build
              →  make -C /src O=/out ...
              →  Image in volume

build.sh  →  docker cp from volume → AnyKernel/Image → zip → out/
```

---

## What to ship in the standalone repo

**Include:**

- `Dockerfile`, `docker-build.sh`, `build.sh`, `clone-kernel.sh`, `.dockerignore`
- `README.md`, `.gitignore`, `STANDALONE_REPO.md` (this file)
- **`AnyKernel/`** — full tree (anykernel.sh, META-INF, tools/, etc.). Build outputs `Image` and `dtbo.img` are in `.gitignore`; the first build fills them.

**Do not include (keep out of the repo or add to `.gitignore`):**

- `kernel_xiaomi_odin/` (huge; users clone or copy their own tree)
- `AnyKernel/Image`, `AnyKernel/dtbo.img` (build outputs; add to `.gitignore`)
- `out/`, `logs/`, `build/`, `clang-r574158/`
- `firmware/`, `reference/`, `tools/` (APKs, zips, etc.)
- `.DS_Store`, other OS cruft

The **standalone repo** = Docker build system + AnyKernel; users run `./clone-kernel.sh` then `./build.sh`.

---

## Making it work as a standalone repo

### Option A: Kernel path as variable (recommended)

In `build.sh`, keep a single place that defines the kernel tree, e.g.:

```bash
KERNEL_SRC="${KERNEL_SRC:-${SCRIPT_DIR}/kernel_xiaomi_odin}"
```

Then users can:

- Clone your standalone repo.
- Clone (or copy) the kernel tree elsewhere.
- Run: `KERNEL_SRC=/path/to/kernel_xiaomi_odin ./build.sh`

No need to clone the kernel inside the same repo.

### Option B: Use clone-kernel.sh (default: NOXCIS/kernel_xiaomi_odin)

- Run `./clone-kernel.sh` to clone [NOXCIS/kernel_xiaomi_odin](https://github.com/NOXCIS/kernel_xiaomi_odin) into `./kernel_xiaomi_odin`. If the directory already exists, the script runs `git pull` instead.
- Override: `./clone-kernel.sh <repo-url>` or `KERNEL_REPO=<url> ./clone-kernel.sh`.
- README: clone this repo → `./clone-kernel.sh` → `./build.sh` (AnyKernel is already in the repo).

### Option C: Submodule or document “clone here”

- Add `kernel_xiaomi_odin` as a **git submodule** (only if you’re okay with a very large repo when they init/update), or
- In README, tell users to clone the kernel into `./kernel_xiaomi_odin` (or set `KERNEL_SRC`).

### AnyKernel (shipped)

- **Ship the full AnyKernel tree** with the repo (anykernel.sh, META-INF, tools/). Add `AnyKernel/Image` and `AnyKernel/dtbo.img` to `.gitignore`; the first `./build.sh` fills them.

---

## Example README for the standalone repo

```markdown
# Odin kernel Docker build system

Reproducible ARM64 kernel build (LLVM/clang, aarch64) in Docker.  
Produces a flashable zip using an AnyKernel-style tree.

## Requirements

- Docker
- Kernel source (Xiaomi Odin or compatible). Use \`./clone-kernel.sh\` to clone it.

## Quick start

1. Clone this repo (includes AnyKernel).
2. Get kernel source: \`./clone-kernel.sh\` (clones NOXCIS/kernel_xiaomi_odin into \`./kernel_xiaomi_odin\`), or set \`KERNEL_SRC=/path/to/kernel\`.
3. Run:
   - \`./build.sh\`           # build default variant
   - \`./build.sh next\`      # KSU-Next only
   - \`./build.sh rebuild\`   # clean + full rebuild

Output: \`out/Odin_<ver>_KSU_NXT_<tag>_<date>.zip\`

## How it works

- **Dockerfile:** Ubuntu 24.04 + LLVM 18 + aarch64 gcc + kernel build deps. No kernel source in the image.
- **build.sh:** Builds the image once, mounts kernel at \`/src\`, runs \`docker-build.sh\` inside the container, then copies \`Image\` from the build volume into AnyKernel and zips to \`out/\`.
- **docker-build.sh:** Runs inside the container; runs \`make -C /src O=/out\` (defconfig + build). See \`STANDALONE_REPO.md\` for details.
```

---

## Example .gitignore for the standalone repo

```gitignore
# Kernel and device trees (users supply these)
kernel_xiaomi_odin/

# Build outputs
out/
logs/
build/

# AnyKernel build outputs (filled by ./build.sh)
AnyKernel/Image
AnyKernel/dtbo.img

# Toolchains / firmware / reference (large or private)
clang-r574158/
firmware/
reference/
tools/

# OS
.DS_Store
*.swp
*.swo
```

---

## Steps to publish on GitHub

1. **Create a new repo** on GitHub (e.g. `odin-kernel-docker-build`).
2. **Clone it locally** (or add a second remote to this project).
3. **Copy the build system and AnyKernel** into that clone:
   - `Dockerfile`, `docker-build.sh`, `build.sh`, `clone-kernel.sh`, `.dockerignore`
   - Full `AnyKernel/` tree (anykernel.sh, META-INF, tools/ — but not `Image` or `dtbo.img`)
   - `README.md`, `.gitignore` (with AnyKernel/Image, AnyKernel/dtbo.img ignored), `STANDALONE_REPO.md`
4. **Commit and push** (no kernel tree, no `out/`, no AnyKernel/Image or dtbo.img).
5. In the README, link to the kernel source repo; users run `./clone-kernel.sh` then `./build.sh`.

Result: a standalone repo with the Docker build system and AnyKernel; users clone → `./clone-kernel.sh` → `./build.sh` to produce the flashable zip.
