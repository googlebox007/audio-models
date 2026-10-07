p = r"I:\GitHub\audio-models\cosyvoice\cosyvoice_pkg\cosyvoice\utils\file_utils.py"
lines = open(p, encoding="utf-8").readlines()
new_block = [
    "def load_wav(wav, target_sr, min_sr=16000):\n",
    "    try:\n",
    "        import soundfile as sf\n",
    "        import numpy as np\n",
    "        data, sr = sf.read(wav, dtype='float32', always_2d=True)\n",
    "        speech = torch.from_numpy(data).float().t()\n",
    "    except Exception:\n",
    "        speech, sr = torchaudio.load(wav, backend='soundfile')\n",
    "        speech = speech.mean(dim=0, keepdim=True)\n",
    "    if sr != target_sr:\n",
    "        assert sr >= min_sr, 'wav sample rate {} must be greater than {}'.format(sr, min_sr)\n",
    "        speech = torchaudio.transforms.Resample(orig_freq=sr, new_freq=target_sr)(speech)\n",
    "    return speech\n",
]
assert lines[43].startswith("def load_wav"), lines[43]
lines[43:50] = new_block
open(p, "w", encoding="utf-8").writelines(lines)
print("patched load_wav")
