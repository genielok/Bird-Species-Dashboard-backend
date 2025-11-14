from perch_hoplite.zoo import model_configs
import numpy as np

waveform = np.zeros(5 * 32000, dtype=np.float32)
model = model_configs.load_model_by_name('perch_v2')
outputs = model.embed(waveform)

print("Embeddings shape:", outputs.embeddings.shape)
print("Predicted labels:", outputs.logits['label'])
