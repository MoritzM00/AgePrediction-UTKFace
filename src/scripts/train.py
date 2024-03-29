"""Training script.

This script is used to train a single model as specified
in the config on the given training and validation dataset.
"""
import logging
import multiprocessing

from src.callbacks import get_callbacks
from src.dataset import get_data_augmentation_pipeline, prepare_for_training
from src.model import build_model_from_cfg

logger = logging.getLogger(__name__)


def train(train_ds, val_ds, cfg):
    """Train the model on the given train and validation datasets.

    Parameters
    ----------
    train_ds : tf.data.Dataset
        Training dataset. Note that this dataset should be shuffled,
        but not prepared for training (no batching etc).
    val_ds : tf.data.Dataset
        Validation dataset.
    cfg : DictConfig
        Configuration object.

    Returns
    -------
    tf.keras.Model
        The trained model.
    """
    if cfg.augment.active:
        data_augmentation_pipeline = get_data_augmentation_pipeline(
            **cfg.augment.factors
        )
    else:
        data_augmentation_pipeline = None

    train_ds = prepare_for_training(
        train_ds,
        batch_size=cfg.train.batch_size,
        shuffle=True,
        augment=cfg.augment.active,
        data_augmentation_pipeline=data_augmentation_pipeline,
        cache=cfg.train.cache_dataset,
    )
    val_ds = prepare_for_training(
        val_ds,
        batch_size=cfg.train.batch_size,
        shuffle=False,
        augment=False,
        cache=cfg.train.cache_dataset,
    )

    callbacks = get_callbacks(val_ds, **cfg.callbacks)

    model, base_model = build_model_from_cfg(cfg, first_stage=True)
    print(model.summary(expand_nested=True))
    history = model.fit(
        train_ds,
        epochs=cfg.train.epochs,
        validation_data=val_ds,
        callbacks=callbacks,
        use_multiprocessing=True,
        workers=multiprocessing.cpu_count(),
    )
    if cfg.model.finetune_base:
        model, base_model = build_model_from_cfg(
            cfg, model=model, base_model=base_model, first_stage=False
        )
        print(model.summary(expand_nested=False))
        initial_epoch = len(history.history["loss"])
        callbacks = get_callbacks(val_ds, initial_epoch=initial_epoch, **cfg.callbacks)
        model.fit(
            train_ds,
            epochs=cfg.train.epochs,
            initial_epoch=initial_epoch,
            validation_data=val_ds,
            callbacks=callbacks,
            use_multiprocessing=True,
            workers=multiprocessing.cpu_count(),
        )
    return model, train_ds, val_ds
