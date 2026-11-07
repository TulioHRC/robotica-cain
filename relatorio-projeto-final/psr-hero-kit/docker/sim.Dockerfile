# HeRo simulator (Genesis), slim build for amd64 and arm64.
#   FLAVOR=cpu  any machine (default)
#   FLAVOR=gpu  NVIDIA GPU with CUDA 12.6 (Linux host + NVIDIA Container Toolkit)
FROM python:3.12-slim-bookworm

ARG FLAVOR=cpu
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# Genesis window: X11 client libraries loaded by pyglet, and OpenGL through libglvnd +
# Mesa (software rendering, or Intel/AMD through /dev/dri). With the NVIDIA runtime
# the host driver provides OpenGL instead of Mesa.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         libgl1 libegl1 libgl1-mesa-dri \
         libx11-6 libxext6 libxrender1 libxrandr2 libxi6 libxinerama1 libxxf86vm1 libxcursor1 libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

COPY docker/sim-requirements.txt docker/psr_slim_stubs.py /tmp/psr/

# Everything in one layer, so the files removed at the end do not stay in the image.
# GPU: cuSOLVER and the cuDNN kernels (~1.2 GB) are never called by the simulator; the
# small libcudnn.so.9 loader stays because libtorch_cuda links to it.
RUN set -eux; \
    case "$FLAVOR" in \
      cpu) index=https://download.pytorch.org/whl/cpu ;; \
      gpu) index=https://download.pytorch.org/whl/cu126 ;; \
      *) echo "FLAVOR must be cpu or gpu" >&2; exit 1 ;; \
    esac; \
    pip install torch==2.14.1 --index-url "$index"; \
    pip install --no-deps genesis-world==1.4.3; \
    pip install -r /tmp/psr/sim-requirements.txt; \
    site=$(python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"); \
    cp /tmp/psr/psr_slim_stubs.py "$site/"; \
    echo "import psr_slim_stubs" > "$site/psr_slim_stubs.pth"; \
    pip uninstall -y triton || true; \
    if [ "$FLAVOR" = gpu ]; then \
      rm -rf "$site/nvidia/cusolver" "$site"/nvidia/cudnn/lib/libcudnn_*.so.*; \
    fi; \
    rm -rf "$site/torch/test" "$site/torch/include" "$site/torch/share/cmake"; \
    find "$site/torch/bin" -mindepth 1 ! -name torch_shm_manager -exec rm -rf {} +; \
    cd "$site/genesis/assets"; \
    find urdf -mindepth 1 -maxdepth 1 ! -name plane -exec rm -rf {} +; \
    find meshes -mindepth 1 -maxdepth 1 ! -name env_sphere -exec rm -rf {} +; \
    rm -rf xml tower; \
    find "$site" -name __pycache__ -prune -exec rm -rf {} +; \
    rm -rf /tmp/psr /root/.cache

WORKDIR /app/sim
COPY sim /app/sim

EXPOSE 11312
CMD ["python", "-m", "psr_sim", "--viewer", "--scenario", "avoid"]
