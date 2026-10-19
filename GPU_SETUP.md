# NVIDIA GPU setup for Sermon-Snip

Sermon-Snip is configured to require NVIDIA GPU inference. It will not silently switch to CPU.

## Why this error occurs

`cublas64_12.dll` is part of the CUDA 12 cuBLAS runtime. Current CTranslate2 GPU builds also require a compatible cuDNN 9 runtime. Installing the NVIDIA display driver alone does not guarantee that these inference libraries are available to Python.

## Fix on Windows

1. Update/restart Windows after installing the latest NVIDIA Studio or Game Ready driver for the RTX 4050, if needed.
2. Install a CUDA 12.x Toolkit from NVIDIA: https://developer.nvidia.com/cuda-downloads
3. Install a compatible cuDNN 9 package for CUDA 12 from NVIDIA: https://developer.nvidia.com/cudnn-downloads
4. Confirm the CUDA `bin` folder and cuDNN `bin` folder are available on `PATH`. A typical CUDA folder is `C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.x\\bin`; use the actual version installed on your computer.
5. Close all Command Prompt windows and restart Sermon-Snip so the updated environment is inherited.
6. Run `nvidia-smi` in Command Prompt to verify that Windows sees the RTX 4050.
7. Run Sermon-Snip and try `medium` first as a GPU smoke test, then try `large-v3`.

Do not download individual DLLs from random DLL websites, and do not copy DLLs into the Python or application folders from untrusted sources.

## If the error remains

- Check that `cublas64_12.dll` exists in the CUDA 12 `bin` directory.
- Check that the cuDNN 9 DLL files are installed and the cuDNN `bin` directory is on `PATH`.
- In a fresh Command Prompt, run `where cublas64_12.dll`.
- If `where` cannot find it, Windows cannot locate the library through `PATH`; correct the installation/path before retrying.
- If the DLL is found but still fails to load, check for a mismatched CUDA/cuDNN/CTranslate2 installation and reinstall compatible versions.

References:
- faster-whisper GPU requirements: https://github.com/SYSTRAN/faster-whisper#gpu
- NVIDIA CUDA Toolkit downloads: https://developer.nvidia.com/cuda-downloads
- NVIDIA cuDNN downloads: https://developer.nvidia.com/cudnn-downloads

Note: Sermon-Snip now registers common CUDA DLL folders before loading faster-whisper and reports GPU errors without using CPU. It cannot install CUDA/cuDNN for you, and this setup still needs to be verified on the target Windows computer.