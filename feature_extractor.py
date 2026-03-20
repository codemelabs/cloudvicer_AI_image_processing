import numpy as np
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing import image

model = MobileNetV2(
    weights="imagenet",
    include_top=False,
    pooling="avg"
)

def extract_vector(img_path):
    img = image.load_img(img_path, target_size=(224, 224))
    x = image.img_to_array(img)
    x = np.expand_dims(x, axis=0)
    x = preprocess_input(x)
    vector = model.predict(x)
    return vector[0].tolist()
