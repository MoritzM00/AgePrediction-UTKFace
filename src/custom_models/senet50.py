"""SENet50 model for Keras.

Source: https://github.com/rcmalli/keras-vggface/blob/master/keras_vggface/models.py#L15
Note: Adapted from the keras-vggface library to support tensorflow 2.*
"""
import warnings

import tensorflow as tf
from keras.utils.data_utils import get_file
from keras.utils.layer_utils import get_source_inputs
from tensorflow.keras import Input, Model, layers
from tensorflow.keras.layers import (
    Activation,
    AveragePooling2D,
    BatchNormalization,
    Conv2D,
    Dense,
    Flatten,
    GlobalAveragePooling2D,
    GlobalMaxPooling2D,
    MaxPooling2D,
    Reshape,
    multiply,
)

SENET50_WEIGHTS_PATH = "https://github.com/rcmalli/keras-vggface/releases/download/v2.0/rcmalli_vggface_tf_senet50.h5"  # noqa: E501
SENET50_WEIGHTS_PATH_NO_TOP = "https://github.com/rcmalli/keras-vggface/releases/download/v2.0/rcmalli_vggface_tf_notop_senet50.h5"  # noqa: E501
VGGFACE_DIR = "data/vggface"


def senet_se_block(input_tensor, stage, block, compress_rate=16, bias=False):
    """Create a Squeeze and Excitation block."""
    conv1_down_name = "conv" + str(stage) + "_" + str(block) + "_1x1_down"
    conv1_up_name = "conv" + str(stage) + "_" + str(block) + "_1x1_up"

    num_channels = int(input_tensor.shape[-1])
    bottle_neck = int(num_channels // compress_rate)

    se = GlobalAveragePooling2D()(input_tensor)
    se = Reshape((1, 1, num_channels))(se)
    se = Conv2D(bottle_neck, (1, 1), use_bias=bias, name=conv1_down_name)(se)
    se = Activation("relu")(se)
    se = Conv2D(num_channels, (1, 1), use_bias=bias, name=conv1_up_name)(se)
    se = Activation("sigmoid")(se)

    x = input_tensor
    x = multiply([x, se])
    return x


def senet_conv_block(
    input_tensor, kernel_size, filters, stage, block, bias=False, strides=(2, 2)
):
    """Create a Convolutional block."""
    filters1, filters2, filters3 = filters
    if tf.keras.backend.image_data_format() == "channels_last":
        bn_axis = 3
    else:
        bn_axis = 1

    bn_eps = 0.0001

    conv1_reduce_name = "conv" + str(stage) + "_" + str(block) + "_1x1_reduce"
    conv1_increase_name = "conv" + str(stage) + "_" + str(block) + "_1x1_increase"
    conv1_proj_name = "conv" + str(stage) + "_" + str(block) + "_1x1_proj"
    conv3_name = "conv" + str(stage) + "_" + str(block) + "_3x3"

    x = Conv2D(
        filters1, (1, 1), use_bias=bias, strides=strides, name=conv1_reduce_name
    )(input_tensor)
    x = BatchNormalization(
        axis=bn_axis, name=conv1_reduce_name + "/bn", epsilon=bn_eps
    )(x)
    x = Activation("relu")(x)

    x = Conv2D(filters2, kernel_size, padding="same", use_bias=bias, name=conv3_name)(x)
    x = BatchNormalization(axis=bn_axis, name=conv3_name + "/bn", epsilon=bn_eps)(x)
    x = Activation("relu")(x)

    x = Conv2D(filters3, (1, 1), name=conv1_increase_name, use_bias=bias)(x)
    x = BatchNormalization(
        axis=bn_axis, name=conv1_increase_name + "/bn", epsilon=bn_eps
    )(x)

    se = senet_se_block(x, stage=stage, block=block, bias=True)

    shortcut = Conv2D(
        filters3, (1, 1), use_bias=bias, strides=strides, name=conv1_proj_name
    )(input_tensor)
    shortcut = BatchNormalization(
        axis=bn_axis, name=conv1_proj_name + "/bn", epsilon=bn_eps
    )(shortcut)

    m = layers.add([se, shortcut])
    m = Activation("relu")(m)
    return m


def senet_identity_block(input_tensor, kernel_size, filters, stage, block, bias=False):
    """Create a senet identity block."""
    filters1, filters2, filters3 = filters
    if tf.keras.backend.image_data_format() == "channels_last":
        bn_axis = 3
    else:
        bn_axis = 1

    bn_eps = 0.0001

    conv1_reduce_name = "conv" + str(stage) + "_" + str(block) + "_1x1_reduce"
    conv1_increase_name = "conv" + str(stage) + "_" + str(block) + "_1x1_increase"
    conv3_name = "conv" + str(stage) + "_" + str(block) + "_3x3"

    x = Conv2D(filters1, (1, 1), use_bias=bias, name=conv1_reduce_name)(input_tensor)
    x = BatchNormalization(
        axis=bn_axis, name=conv1_reduce_name + "/bn", epsilon=bn_eps
    )(x)
    x = Activation("relu")(x)

    x = Conv2D(filters2, kernel_size, padding="same", use_bias=bias, name=conv3_name)(x)
    x = BatchNormalization(axis=bn_axis, name=conv3_name + "/bn", epsilon=bn_eps)(x)
    x = Activation("relu")(x)

    x = Conv2D(filters3, (1, 1), name=conv1_increase_name, use_bias=bias)(x)
    x = BatchNormalization(
        axis=bn_axis, name=conv1_increase_name + "/bn", epsilon=bn_eps
    )(x)

    se = senet_se_block(x, stage=stage, block=block, bias=True)

    m = layers.add([se, input_tensor])
    m = Activation("relu")(m)

    return m


def SENet50(
    include_top=True,
    weights="vggface",
    input_tensor=None,
    input_shape=None,
    pooling=None,
    classes=8631,
):
    """Instantiate the SENet50 architecture."""
    w, h, _ = input_shape
    if (w, h) < (197, 197):
        raise ValueError("Minimum input size for SENet50 is 197x197")
    if input_tensor is None:
        img_input = Input(shape=input_shape)
    else:
        if not tf.keras.is_keras_tensor(input_tensor):
            img_input = Input(tensor=input_tensor, shape=input_shape)
        else:
            img_input = input_tensor
    if tf.keras.backend.image_data_format() == "channels_last":
        bn_axis = 3
    else:
        bn_axis = 1

    bn_eps = 0.0001

    x = Conv2D(
        64, (7, 7), use_bias=False, strides=(2, 2), padding="same", name="conv1/7x7_s2"
    )(img_input)
    x = BatchNormalization(axis=bn_axis, name="conv1/7x7_s2/bn", epsilon=bn_eps)(x)
    x = Activation("relu")(x)
    x = MaxPooling2D((3, 3), strides=(2, 2))(x)

    x = senet_conv_block(x, 3, [64, 64, 256], stage=2, block=1, strides=(1, 1))
    x = senet_identity_block(x, 3, [64, 64, 256], stage=2, block=2)
    x = senet_identity_block(x, 3, [64, 64, 256], stage=2, block=3)

    x = senet_conv_block(x, 3, [128, 128, 512], stage=3, block=1)
    x = senet_identity_block(x, 3, [128, 128, 512], stage=3, block=2)
    x = senet_identity_block(x, 3, [128, 128, 512], stage=3, block=3)
    x = senet_identity_block(x, 3, [128, 128, 512], stage=3, block=4)

    x = senet_conv_block(x, 3, [256, 256, 1024], stage=4, block=1)
    x = senet_identity_block(x, 3, [256, 256, 1024], stage=4, block=2)
    x = senet_identity_block(x, 3, [256, 256, 1024], stage=4, block=3)
    x = senet_identity_block(x, 3, [256, 256, 1024], stage=4, block=4)
    x = senet_identity_block(x, 3, [256, 256, 1024], stage=4, block=5)
    x = senet_identity_block(x, 3, [256, 256, 1024], stage=4, block=6)

    x = senet_conv_block(x, 3, [512, 512, 2048], stage=5, block=1)
    x = senet_identity_block(x, 3, [512, 512, 2048], stage=5, block=2)
    x = senet_identity_block(x, 3, [512, 512, 2048], stage=5, block=3)

    x = AveragePooling2D((7, 7), name="avg_pool")(x)

    if include_top:
        x = Flatten()(x)
        x = Dense(classes, activation="softmax", name="classifier")(x)
    else:
        if pooling is not None:
            if pooling == "avg":
                x = GlobalAveragePooling2D()(x)
            elif pooling == "max":
                x = GlobalMaxPooling2D()(x)

    # Ensure that the model takes into account
    # any potential predecessors of `input_tensor`.
    if input_tensor is not None:
        inputs = get_source_inputs(input_tensor)
    else:
        inputs = img_input
    # Create model.
    model = Model(inputs, x, name="vggface_senet50")

    # load weights
    if weights == "vggface":
        if include_top:
            weights_path = get_file(
                "rcmalli_vggface_tf_senet50.h5",
                SENET50_WEIGHTS_PATH,
                cache_subdir=VGGFACE_DIR,
            )
        else:
            weights_path = get_file(
                "rcmalli_vggface_tf_notop_senet50.h5",
                SENET50_WEIGHTS_PATH_NO_TOP,
                cache_subdir=VGGFACE_DIR,
            )
        model.load_weights(weights_path)

        if (
            tf.keras.backend.image_data_format() == "channels_first"
            and tf.keras.backend() == "tensorflow"
        ):
            warnings.warn(
                "You are using the TensorFlow backend, yet you "
                "are using the Theano "
                "image data format convention "
                '(`image_data_format="channels_first"`). '
                "For best performance, set "
                '`image_data_format="channels_last"` in '
                "your Keras config "
                "at ~/.keras/keras.json."
            )
    elif weights is not None:
        model.load_weights(weights)

    return model
