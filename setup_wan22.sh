!rm -rf /kaggle/working/ComfyUI
%cd /kaggle/working

!git clone https://github.com/comfyanonymous/ComfyUI.git

%cd /kaggle/working/ComfyUI

!pip install -r requirements.txt


!rm -rf /kaggle/working/ComfyUI/models/text_encoders
!rm -rf /kaggle/working/ComfyUI/models/vae
!rm -rf /kaggle/working/ComfyUI/models/diffusion_models
!mkdir -p /kaggle/tmp/models/text_encoders/
!mkdir -p /kaggle/tmp/models/diffusion_models/
!mkdir -p /kaggle/tmp/models/vae

!pip install --upgrade huggingface_hub
!export HF_TOKEN="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"

!hf download Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors --local-dir /kaggle/tmp/models/diffusion_models/

!hf download Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors --local-dir /kaggle/tmp/models/text_encoders/

!hf download Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/vae/wan2.2_vae.safetensors --local-dir /kaggle/tmp/models/vae/



!ln -s /kaggle/tmp/models/diffusion_models/split_files/diffusion_models /kaggle/working/ComfyUI/models/diffusion_models
!ln -s /kaggle/tmp/models/vae/split_files/vae /kaggle/working/ComfyUI/models/vae
!ln -s /kaggle/tmp/models/text_encoders/split_files/text_encoders /kaggle/working/ComfyUI/models/text_encoders
!ls -R /kaggle/tmp/models/diffusion_models/split_files/diffusion_models /kaggle/working/ComfyUI/models/diffusion_models
!ls -R /kaggle/tmp/models/vae/split_files/vae /kaggle/working/ComfyUI/models/vae
!ls -R /kaggle/tmp/models/text_encoders/split_files/text_encoders /kaggle/working/ComfyUI/models/text_encoders


# Start Comfy
%cd /kaggle/working/ComfyUI

!pip install transformers -U

import os
import subprocess

log = open("/kaggle/working/comfyui.log", "w")
current_env = os.environ.copy()
current_env["CUDA_VISIBLE_DEVICES"] = "0"

server = subprocess.Popen(
    ["python", "main.py", "--listen", "127.0.0.1", "--port", "8188","--lowvram"],
    stdout=log,
    stderr=subprocess.STDOUT,
    env=current_env
)

print("ComfyUI PID:", server.pid)

#!ps aux | grep "main.py"
#!kill 314
!tail -10 /kaggle/working/comfyui.log



!mkdir -p /kaggle/working/stories

!cp -rf /kaggle/input/datasets/anantpixel8pro/bhagwan-stories /kaggle/working/stories

