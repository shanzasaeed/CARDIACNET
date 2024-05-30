# -*- coding: utf-8 -*-
"""Model.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1KqZrAt--JVDZvmWah9fitDMhrW3ScE9O
"""

from data import train_gen, val_gen

db_train = train_gen(base_dir='/kaggle/working/training',
                            split="train",
                            num=None,
                            transform=None,sample_list=sample_list)
#total 1312 samples
images=[]
for i in range(0,len(db_train)):
    images+=db_train[i]['image']
images=np.stack(images, axis=0)

labels=[]
for i in range(0,len(db_train)):
    labels+=db_train[i]['label']
labels=np.stack(labels, axis=0)

images=images.reshape((1902, 256, 256, 1))
labels=labels.reshape((1902, 256, 256, 1))

db_val = val_gen(base_dir='/kaggle/working/testing/',
                            split="val",
                            num=None,
                            transform=None,sample_list_val=sample_list_val)

images_val=[]
for i in range(0,len(db_val)):
    images_val+=db_val[i]['image']
images_val=np.stack(images_val, axis=0)
labels_val=[]
for i in range(0,len(db_val)):
    labels_val+=db_val[i]['label']
labels_val=np.stack(labels_val, axis=0)

images_val=images_val.reshape((1076, 256, 256, 1))
labels_val=labels_val.reshape((1076, 256, 256, 1))

import tensorflow as tf
from tensorflow.keras import backend as K

def dice_coef(y_true, y_pred, smooth=1):
    y_true = K.cast(y_true, 'float32')
    y_pred = K.cast(y_pred, 'float32')
    
    y_true_f = K.flatten(y_true)
    y_pred_f = K.flatten(y_pred)
    
    intersection = K.sum(y_true_f * y_pred_f)
    union = K.sum(y_true_f) + K.sum(y_pred_f)
    
    dice = (2. * intersection + smooth) / (union + smooth)
    return dice


def iou_coef(y_true, y_pred, smooth=1):
    y_true = K.cast(y_true, 'float32')
    y_pred = K.cast(y_pred, 'float32')
    
    y_true_f = K.flatten(y_true)
    y_pred_f = K.flatten(y_pred)
    
    intersection = K.sum(y_true_f * y_pred_f)
    total = K.sum(y_true_f) + K.sum(y_pred_f)
    union = total - intersection
    
    iou = (intersection + smooth) / (union + smooth)
    return iou

def dice_loss(y_true, y_pred):
    return 1 - dice_coef(y_true, y_pred)

def matthews_correlation_coefficient(y_true, y_pred):
    y_true = K.cast(y_true, 'float32')
    y_pred = K.cast(y_pred, 'float32')
    tp = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
    tn = K.sum(K.round(K.clip((1 - y_true) * (1 - y_pred), 0, 1)))
    fp = K.sum(K.round(K.clip((1 - y_true) * y_pred, 0, 1)))
    fn = K.sum(K.round(K.clip(y_true * (1 - y_pred), 0, 1)))

    num = tp * tn - fp * fn
    den = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    return num / K.sqrt(den + K.epsilon())

import tensorflow as tf
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, UpSampling2D, concatenate, Activation, Add, Multiply, BatchNormalization
from tensorflow.keras.models import Model

def conv_block(input_tensor, num_filters):
    #x = Conv2D(num_filters, (3, 3), padding="same", kernel_regularizer=regularizers.l2())(input_tensor)
    x = Conv2D(num_filters, (3, 3), padding="same",kernel_initializer="he_normal")(input_tensor)
    x = Dropout(0.5)(x)
    x = BatchNormalization()(x)
    x = Activation("relu")(x)
    x = Conv2D(num_filters, (3, 3), padding="same")(x)
    x = BatchNormalization()(x)
    x = Activation("relu")(x)
    return x

def attention_gate(input_tensor, gating_tensor, num_filters):
    gate_shape = gating_tensor.shape
    x = Conv2D(num_filters, (1, 1), padding='same')(input_tensor)
    g = Conv2D(num_filters, (1, 1), padding='same')(gating_tensor)
    x = UpSampling2D(size=(gate_shape[1] // x.shape[1], gate_shape[2] // x.shape[2]))(x)
    x = Add()([x, g])
    x = Activation('relu')(x)
    x = Conv2D(1, (1, 1), padding='same')(x)
    x = Activation('sigmoid')(x)
    return Multiply()([input_tensor, x])

def build_attention_unet(input_shape=(256, 256, 1)):
    inputs = Input(input_shape)

    # Encoder
    x0_0 = conv_block(inputs, 32)
    p0 = MaxPooling2D((2, 2))(x0_0)
    x1_0 = conv_block(p0, 64)
    p1 = MaxPooling2D((2, 2))(x1_0)
    x2_0 = conv_block(p1, 128)
    p2 = MaxPooling2D((2, 2))(x2_0)
    x3_0 = conv_block(p2, 256)
    p3 = MaxPooling2D((2, 2))(x3_0)
    x4_0 = conv_block(p3, 512)

    # Intermediate Levels
    x0_1 = conv_block(concatenate([x0_0, UpSampling2D()(x1_0)]), 32)
    x1_1 = conv_block(concatenate([x1_0, UpSampling2D()(x2_0)]), 64)
    x2_1 = conv_block(concatenate([x2_0, UpSampling2D()(x3_0)]), 128)
    #Ax3_1 = conv_block(concatenate([x3_0, UpSampling2D()(x4_0)]), 256)
    x3_1 = conv_block(attention_gate(x3_0, UpSampling2D()(x4_0),256), 256)
    
    x0_2 = conv_block(concatenate([x0_1, UpSampling2D()(x1_1)]), 32)
    x1_2 = conv_block(concatenate([x1_1, UpSampling2D()(x2_1)]), 64)
    #Ax2_2 = conv_block(concatenate([x2_1, UpSampling2D()(x3_1)]), 128)
    x2_2 = conv_block(attention_gate(concatenate([x2_1,x2_0]),UpSampling2D()(x3_1),128), 128)
    
    x0_3 = conv_block(concatenate([x0_2, UpSampling2D()(x1_2)]), 32)
    #Ax1_3 = conv_block(concatenate([x1_2, UpSampling2D()(x2_2)]), 64)
    x1_3 = conv_block(attention_gate(concatenate([x1_0,x1_1,x1_2]),UpSampling2D()(x2_2),64), 64)   

    x0_4 = conv_block(attention_gate(concatenate([x0_0,x0_1,x0_2,x0_3]),UpSampling2D()(x1_3),32), 32)

    # Final output
    outputs = Conv2D(1, (1, 1), activation='sigmoid')(x0_4)

    model = Model(inputs=[inputs], outputs=[outputs])
    return model

# Create the model
model = build_attention_unet()
optimizer = Adam(learning_rate=0.001) 
model.compile(optimizer=optimizer, loss=dice_loss, metrics=['accuracy',dice_coef,iou_coef])
model.summary()

filepath = "model.keras"

earlystopper = EarlyStopping(patience=10, verbose=1)

checkpoint = ModelCheckpoint(filepath, monitor='val_loss', verbose=1, 
                             save_best_only=True, mode='min')
callbacks_list = [earlystopper, checkpoint]
history=model.fit(images, labels, epochs=60, batch_size=16, validation_data=(images_val,labels_val),callbacks=callbacks_list)
# Save the model weights
model.save_weights('model_weights.weights.h5')

evaluation = model.evaluate(images_val, labels_val)
print(f"Test Loss: {evaluation[0]}, Test Accuracy: {evaluation[1]}")

import matplotlib.pyplot as plt

predictions = model.predict(images_val)

# Visualize some predictions alongside actual images
for i in range(5):
    plt.figure(figsize=(12, 4))

    plt.subplot(1, 3, 1)
    plt.title("Input Image")
    plt.imshow(images_val[i].reshape(256, 256), cmap='gray')

    plt.subplot(1, 3, 2)
    plt.title("Actual Mask")
    plt.imshow(labels_val[i].reshape(256, 256), cmap='gray')

    plt.subplot(1, 3, 3)
    plt.title("Predicted Mask")
    plt.imshow(predictions[i].reshape(256, 256), cmap='gray')

    plt.show()
