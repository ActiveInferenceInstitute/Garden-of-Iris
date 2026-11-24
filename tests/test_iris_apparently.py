"""Tiny component checks, not training or scientific qualification.

The parent must run these with the declared TensorFlow/scikit-learn runtime;
a missing-component skip is not acceptance evidence.
"""

import math

import numpy as np
import pandas as pd
import pytest

tf = pytest.importorskip("tensorflow")
pytest.importorskip("sklearn")
import iris_apparently as sketch


def _data():
    return pd.DataFrame({
        "text": [f"unique{i}" for i in range(10)],
        "source_id": [f"source{i}" for i in range(10)],
        "timestamp": pd.date_range("2024-01-01", periods=10).astype(str),
    })


def _config(prepared):
    return dict(
        num_layers=1, d_model=4, num_heads=2, dff=8,
        input_vocab_size=50, target_vocab_size=50,
        max_position_encoding=prepared["max_length"],
        num_sources=len(prepared["source_map"]) + 1, dropout_rate=0,
    )


def test_masked_loss_uses_logits_and_ignores_padding():
    labels = tf.constant([[1, 0]])
    logits = tf.constant([[[0., 2., 0.], [-100., 100., 0.]]])
    expected = math.log1p(2 * math.exp(-2))
    assert float(sketch.masked_token_loss(labels, logits)) == pytest.approx(expected)
    changed_padding = tf.constant([[[0., 2., 0.], [100., -100., 0.]]])
    assert float(sketch.masked_token_loss(labels, changed_padding)) == pytest.approx(expected)
    assert float(sketch.masked_token_loss(tf.zeros((1, 2), tf.int32), logits)) == 0


def test_masked_accuracy_counts_valid_tokens_across_batches():
    metric = sketch.MaskedTokenAccuracy()
    metric.update_state(tf.constant([[1, 0]]), tf.constant([[[0., 3., 0.], [0., 3., 0.]]]))
    metric.update_state(tf.constant([[2, 2, 2]]), tf.constant([[[3., 0., 0.]] * 3]))
    assert float(metric.result()) == pytest.approx(0.25)
    metric.reset_state()
    metric.update_state(tf.zeros((1, 2), tf.int32), tf.ones((1, 2, 3)))
    assert float(metric.result()) == 0


def test_preprocessing_fits_training_rows_only_and_has_explicit_unknown_indices():
    data = _data()
    prepared = sketch.prepare_training_data(data, vocab_size=50, max_length=4, d_model=4, seed=7)
    repeated = sketch.prepare_training_data(data, vocab_size=50, max_length=4, d_model=4, seed=7)
    assert prepared["train_indices"] == repeated["train_indices"]
    assert prepared["validation_indices"] == repeated["validation_indices"]
    assert set(prepared["train_indices"]).isdisjoint(prepared["validation_indices"])
    for index in prepared["validation_indices"]:
        row = data.loc[index]
        assert row["text"] not in prepared["tokenizer"].word_index
        assert row["source_id"] not in prepared["source_map"]
        assert pd.Timestamp(row["timestamp"]) not in prepared["timestamp_map"]
    _, source_ids, timestamp_ids = prepared["validation"]
    np.testing.assert_array_equal(source_ids, 0)
    np.testing.assert_array_equal(timestamp_ids, 0)
    np.testing.assert_array_equal(prepared["temporal"][0], np.zeros(4))
    for original, again in zip(prepared["training"], repeated["training"]):
        np.testing.assert_array_equal(original, again)


def test_attention_masks_padded_keys_without_changing_the_objective():
    prepared = sketch.prepare_training_data(_data(), vocab_size=50, max_length=3, d_model=4, seed=7)
    model = sketch.DemocraticLLM(**_config(prepared), temporal_emb=prepared["temporal"])
    logits = model([tf.constant([[1, 0, 2]]), tf.constant([1]), tf.constant([1])], training=False)
    assert tuple(logits.shape) == (1, 3, 50)
    attention = model.attention_weights
    masked = [
        attention["encoder"]["encoder_layer1_block1"],
        attention["decoder"]["decoder_layer1_block1"],
        attention["decoder"]["decoder_layer1_block2"],
    ]
    for weights in masked:
        np.testing.assert_allclose(weights.numpy()[..., 1], 0, atol=1e-7)
    assert np.isfinite(logits.numpy()).all()


def test_model_bundle_round_trip_preserves_predictions_and_preprocessing(tmp_path):
    prepared = sketch.prepare_training_data(_data(), vocab_size=50, max_length=4, d_model=4, seed=7)
    config = _config(prepared)
    model = sketch.DemocraticLLM(**config, temporal_emb=prepared["temporal"])
    inputs = [tensor[:1] for tensor in prepared["training"]]
    before = model(inputs, training=False).numpy()
    sketch.save_training_bundle(model, prepared, config, tmp_path)
    loaded = sketch.load_training_bundle(tmp_path)
    np.testing.assert_allclose(loaded["model"](inputs, training=False).numpy(), before, atol=1e-6)
    assert loaded["source_map"] == prepared["source_map"]
    assert loaded["timestamp_map"] == prepared["timestamp_map"]
    sample = ["unique0 unknownword"]
    assert loaded["tokenizer"].texts_to_sequences(sample) == prepared["tokenizer"].texts_to_sequences(sample)
    assert loaded["metadata"]["data_sha256"] == prepared["data_sha256"]
    with (tmp_path / "model.weights.h5").open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(ValueError, match="weights"):
        sketch.load_training_bundle(tmp_path)


def test_training_cli_requires_explicit_output_custody_before_reading_data(monkeypatch):
    monkeypatch.setattr(sketch, "load_csv", lambda path: pytest.fail("missing output path reached private data"))
    with pytest.raises(SystemExit) as error:
        sketch.main(["authorized.csv"])
    assert error.value.code == 2


def test_bundle_save_preserves_an_occupied_output_directory(tmp_path):
    prepared = sketch.prepare_training_data(_data(), vocab_size=50, max_length=4, d_model=4, seed=7)
    config = _config(prepared)
    model = sketch.DemocraticLLM(**config, temporal_emb=prepared["temporal"])
    sentinel = tmp_path / "model.weights.h5"
    sentinel.write_bytes(b"historical sentinel")
    with pytest.raises(FileExistsError):
        sketch.save_training_bundle(model, prepared, config, tmp_path)
    assert sentinel.read_bytes() == b"historical sentinel"
    assert list(tmp_path.iterdir()) == [sentinel]
