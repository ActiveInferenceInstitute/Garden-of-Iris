"""DemocraticLLM — a sketch of the Iris transformer architecture.

An unfinished TensorFlow/Keras attempt at a "democratic" language model: a
Transformer encoder-decoder whose layers add extra attention blocks over
*source embeddings* (one learned embedding per contributing source) and
sinusoidal *temporal embeddings* derived from timestamps.

Status: structurally repaired so that the module imports and the documented
training flow in ``main()`` is consistent with ``DemocraticLLM.call``, but it
remains an unverified sketch. Training it requires TensorFlow and a CSV with
``text``, ``source_id``, and ``timestamp`` columns; no such dataset is
committed to this repository.
"""

import sys
import argparse
import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.model_selection import train_test_split
from tensorflow.keras import layers
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.preprocessing.text import Tokenizer


# Load the CSV file
def load_csv(file_path):
    data = pd.read_csv(file_path)
    return data


# Preprocess the data
def preprocess_data(data, tokenizer, max_length, source_id_to_idx, timestamp_to_idx):
    text_data = data['text'].tolist()
    source_data = data['source_id'].apply(lambda value: source_id_to_idx.get(value, 0)).tolist()
    timestamp_data = data['timestamp'].apply(lambda value: timestamp_to_idx.get(pd.Timestamp(value), 0)).tolist()

    # Tokenize the text data
    sequences = tokenizer.texts_to_sequences(text_data)
    input_ids = pad_sequences(sequences, maxlen=max_length, padding='post', truncating='post')

    return input_ids, source_data, timestamp_data


# Create tensor representations for the data
def create_tensors(input_ids, source_data, timestamp_data):
    input_ids_tensor = tf.convert_to_tensor(input_ids, dtype=tf.int32)
    source_data_tensor = tf.convert_to_tensor(source_data, dtype=tf.int32)
    timestamp_data_tensor = tf.convert_to_tensor(timestamp_data, dtype=tf.int32)

    return input_ids_tensor, source_data_tensor, timestamp_data_tensor


def create_sinusoidal_embeddings(data, d_model):
    # Assuming data is a list of timestamps
    num_timestamps = len(data)
    temporal_emb = np.zeros((num_timestamps, d_model))

    # Create a mapping from timestamps to indices in the temporal_emb tensor
    timestamp_to_idx = {timestamp: idx for idx, timestamp in enumerate(data)}

    # Compute sinusoidal embeddings
    for idx, timestamp in enumerate(data):
        position = idx
        timestamp = pd.Timestamp(timestamp)
        div_term = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))

        second = timestamp.second / 60
        minute = timestamp.minute / 60
        hour = timestamp.hour / 24
        day = timestamp.day / 31
        month = timestamp.month / 12
        year = (timestamp.year - 1970) / 50  # Assuming a range of 50 years, adjust as needed

        time_factors = [second, minute, hour, day, month, year]
        sinusoidal_factors = np.array(time_factors)[:, np.newaxis] * div_term

        # Apply sin and cos to even and odd indices, summing over the six
        # time components (second through year) per frequency band
        temporal_emb[position, 0::2] = np.sum(np.sin(sinusoidal_factors), axis=0)
        temporal_emb[position, 1::2] = np.sum(np.cos(sinusoidal_factors), axis=0)

    return tf.convert_to_tensor(temporal_emb, dtype=tf.float32), timestamp_to_idx


def positional_encoding(position, d_model):
    angle_rads = get_angles(np.arange(position)[:, np.newaxis],
                            np.arange(d_model)[np.newaxis, :],
                            d_model)
    # Apply sin to even indices in the array; 2i
    angle_rads[:, 0::2] = np.sin(angle_rads[:, 0::2])

    # Apply cos to odd indices in the array; 2i+1
    angle_rads[:, 1::2] = np.cos(angle_rads[:, 1::2])

    pos_encoding = angle_rads[np.newaxis, ...]

    return tf.cast(pos_encoding, dtype=tf.float32)


def get_angles(pos, i, d_model):
    angle_rates = 1 / np.power(10000, (2 * (i // 2)) / np.float32(d_model))
    return pos * angle_rates


@tf.keras.utils.register_keras_serializable(package="Iris")
def masked_token_loss(targets, logits):
    losses = tf.keras.losses.sparse_categorical_crossentropy(targets, logits, from_logits=True)
    weights = tf.cast(tf.not_equal(tf.cast(targets, tf.int32), 0), losses.dtype)
    return tf.math.divide_no_nan(tf.reduce_sum(losses * weights), tf.reduce_sum(weights))


@tf.keras.utils.register_keras_serializable(package="Iris")
class MaskedTokenAccuracy(tf.keras.metrics.SparseCategoricalAccuracy):
    def __init__(self, name="masked_token_accuracy", **kwargs):
        super().__init__(name=name, **kwargs)

    def update_state(self, y_true, y_pred, sample_weight=None):
        weights = tf.cast(tf.not_equal(tf.cast(y_true, tf.int32), 0), self.dtype)
        if sample_weight is not None:
            supplied = tf.cast(sample_weight, self.dtype)
            if supplied.shape.rank == 1 and weights.shape.rank == 2:
                supplied = supplied[:, tf.newaxis]
            weights *= supplied
        return super().update_state(y_true, y_pred, sample_weight=weights)


def prepare_training_data(data, *, vocab_size=30000, max_length=256, d_model=512, seed=42):
    """Retain the existing random-row split, fitting learned preprocessing on training rows only."""
    data = data.copy()
    if not {"text", "source_id", "timestamp"}.issubset(data.columns):
        raise ValueError("Training CSV requires text, source_id and timestamp")
    if data[["text", "source_id", "timestamp"]].isna().any().any():
        raise ValueError("Training rows cannot contain missing text/source/timestamp")
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    train, validation = train_test_split(data, train_size=0.8, random_state=seed)
    tokenizer = Tokenizer(num_words=vocab_size, oov_token="<OOV>")
    tokenizer.fit_on_texts(train["text"])
    source_map = {source: index + 1 for index, source in enumerate(train["source_id"].unique())}
    timestamps = list(train["timestamp"].drop_duplicates())
    temporal, timestamp_map = create_sinusoidal_embeddings(timestamps, d_model)
    temporal = tf.concat([tf.zeros((1, d_model), dtype=tf.float32), temporal], axis=0)
    timestamp_map = {pd.Timestamp(value): index + 1 for value, index in timestamp_map.items()}
    training = create_tensors(*preprocess_data(train, tokenizer, max_length, source_map, timestamp_map))
    held_out = create_tensors(*preprocess_data(validation, tokenizer, max_length, source_map, timestamp_map))
    return {
        "training": training, "validation": held_out, "tokenizer": tokenizer,
        "source_map": source_map, "timestamp_map": timestamp_map, "temporal": temporal,
        "train_indices": train.index.tolist(), "validation_indices": validation.index.tolist(),
        "seed": seed, "max_length": max_length,
        "data_sha256": hashlib.sha256(
            data.to_json(orient="split", date_format="iso").encode("utf-8")
        ).hexdigest(),
    }


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_training_bundle(model, prepared, config, directory):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError("Select a fresh private bundle directory; existing outputs are preserved")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    model.save_weights(str(directory / "model.weights.h5"))
    sources = [
        [value.item() if isinstance(value, np.generic) else value, index]
        for value, index in prepared["source_map"].items()
    ]
    metadata = {
        "schema": "iris-sketch-bundle/v1", "config": config,
        "tokenizer": prepared["tokenizer"].to_json(), "sources": sources,
        "timestamps": [[value.isoformat(), index] for value, index in prepared["timestamp_map"].items()],
        "temporal": np.asarray(prepared["temporal"]).tolist(),
        "seed": prepared["seed"], "max_length": prepared["max_length"],
        "train_indices": prepared["train_indices"], "validation_indices": prepared["validation_indices"],
        "data_sha256": prepared["data_sha256"],
        "weights_sha256": _file_sha256(directory / "model.weights.h5"),
        "program_sha256": _file_sha256(__file__),
        "versions": {"tensorflow": tf.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        "objective": "existing same-sequence encoder-decoder; research qualification pending",
        "unseen_categories": "index 0; timestamp vector is zero; source embedding is untrained",
        "evaluation": "existing seeded random-row split; research evaluation policy pending",
    }
    (directory / "preprocessing.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def load_training_bundle(directory):
    directory = Path(directory)
    metadata = json.loads((directory / "preprocessing.json").read_text(encoding="utf-8"))
    if metadata.get("schema") != "iris-sketch-bundle/v1":
        raise ValueError("Unsupported Iris bundle schema")
    if metadata.get("weights_sha256") != _file_sha256(directory / "model.weights.h5"):
        raise ValueError("Iris bundle weights do not match preprocessing metadata")
    model = DemocraticLLM(**metadata["config"], temporal_emb=np.asarray(metadata["temporal"]))
    length = metadata["max_length"]
    model([tf.zeros((1, length), tf.int32), tf.zeros((1,), tf.int32), tf.zeros((1,), tf.int32)])
    model.load_weights(str(directory / "model.weights.h5"))
    return {
        "model": model,
        "tokenizer": tf.keras.preprocessing.text.tokenizer_from_json(metadata["tokenizer"]),
        "source_map": dict(metadata["sources"]),
        "timestamp_map": {pd.Timestamp(value): index for value, index in metadata["timestamps"]},
        "max_length": length, "metadata": metadata,
    }


def create_padding_mask(seq):
    # Standard padding mask: 1.0 where the token id is 0 (padding).
    seq = tf.cast(tf.math.equal(seq, 0), tf.float32)
    return seq[:, tf.newaxis, tf.newaxis, :]  # (batch_size, 1, 1, seq_len)


def create_look_ahead_mask(size):
    # Standard causal (look-ahead) mask for decoder self-attention.
    mask = 1 - tf.linalg.band_part(tf.ones((size, size)), -1, 0)
    return mask  # (size, size)


def point_wise_feed_forward_network(d_model, dff):
    return tf.keras.Sequential([
        tf.keras.layers.Dense(dff, activation='relu'),  # (batch_size, seq_len, dff)
        tf.keras.layers.Dense(d_model)  # (batch_size, seq_len, d_model)
    ])


# Define the necessary layers and components for the Iris model
class MultiHeadAttention(layers.Layer):
    def __init__(self, d_model, num_heads):
        super(MultiHeadAttention, self).__init__()
        self.num_heads = num_heads
        self.d_model = d_model

        assert d_model % self.num_heads == 0

        self.depth = d_model // self.num_heads

        self.wq = tf.keras.layers.Dense(d_model)
        self.wk = tf.keras.layers.Dense(d_model)
        self.wv = tf.keras.layers.Dense(d_model)

        self.dense = tf.keras.layers.Dense(d_model)

    def split_heads(self, x, batch_size):
        x = tf.reshape(x, (batch_size, -1, self.num_heads, self.depth))
        return tf.transpose(x, perm=[0, 2, 1, 3])

    def call(self, v, k, q, mask):
        batch_size = tf.shape(q)[0]

        q = self.wq(q)
        k = self.wk(k)
        v = self.wv(v)

        q = self.split_heads(q, batch_size)
        k = self.split_heads(k, batch_size)
        v = self.split_heads(v, batch_size)

        scaled_attention, attention_weights = self.scaled_dot_product_attention(q, k, v, mask)

        scaled_attention = tf.transpose(scaled_attention, perm=[0, 2, 1, 3])
        concat_attention = tf.reshape(scaled_attention, (batch_size, -1, self.d_model))

        output = self.dense(concat_attention)
        return output, attention_weights

    def scaled_dot_product_attention(self, q, k, v, mask):
        matmul_qk = tf.matmul(q, k, transpose_b=True)

        dk = tf.cast(tf.shape(k)[-1], tf.float32)
        scaled_attention_logits = matmul_qk / tf.math.sqrt(dk)

        if mask is not None:
            scaled_attention_logits += (mask * -1e9)

        attention_weights = tf.nn.softmax(scaled_attention_logits, axis=-1)
        output = tf.matmul(attention_weights, v)

        return output, attention_weights


class EncoderLayer(tf.keras.layers.Layer):
    def __init__(self, d_model, num_heads, dff, rate=0.1):
        super(EncoderLayer, self).__init__()

        self.mha1 = MultiHeadAttention(d_model, num_heads)
        self.mha2 = MultiHeadAttention(d_model, num_heads)

        self.ffn = point_wise_feed_forward_network(d_model, dff)

        self.layernorm1 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.layernorm3 = tf.keras.layers.LayerNormalization(epsilon=1e-6)

        self.dropout1 = tf.keras.layers.Dropout(rate)
        self.dropout2 = tf.keras.layers.Dropout(rate)
        self.dropout3 = tf.keras.layers.Dropout(rate)

    def call(self, x, training, mask, source_embeddings):
        attn1, attn_weights_block1 = self.mha1(v=x, k=x, q=x, mask=mask)  # self-attention
        attn1 = self.dropout1(attn1, training=training)
        out1 = self.layernorm1(attn1 + x)

        if source_embeddings is not None:
            attn2, attn_weights_block2 = self.mha2(v=source_embeddings, k=source_embeddings, q=out1, mask=None)  # source attention
            attn2 = self.dropout2(attn2, training=training)
            out2 = self.layernorm2(attn2 + out1)
        else:
            attn_weights_block2 = None
            out2 = out1

        ffn_output = self.ffn(out2)
        ffn_output = self.dropout3(ffn_output, training=training)
        out3 = self.layernorm3(ffn_output + out2)

        return out3, attn_weights_block1, attn_weights_block2


class DecoderLayer(tf.keras.layers.Layer):
    def __init__(self, d_model, num_heads, dff, rate=0.1):
        super(DecoderLayer, self).__init__()

        self.mha1 = MultiHeadAttention(d_model, num_heads)
        self.mha2 = MultiHeadAttention(d_model, num_heads)
        self.mha3 = MultiHeadAttention(d_model, num_heads)

        self.ffn = point_wise_feed_forward_network(d_model, dff)

        self.layernorm1 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.layernorm3 = tf.keras.layers.LayerNormalization(epsilon=1e-6)

        self.dropout1 = tf.keras.layers.Dropout(rate)
        self.dropout2 = tf.keras.layers.Dropout(rate)
        self.dropout3 = tf.keras.layers.Dropout(rate)

    def call(self, x, enc_output, training, look_ahead_mask, padding_mask, source_embeddings):
        attn1, attn_weights_block1 = self.mha1(v=x, k=x, q=x, mask=look_ahead_mask)  # self-attention
        attn1 = self.dropout1(attn1, training=training)
        out1 = self.layernorm1(attn1 + x)

        attn2, attn_weights_block2 = self.mha2(v=enc_output, k=enc_output, q=out1, mask=padding_mask)  # encoder-decoder attention
        attn2 = self.dropout2(attn2, training=training)
        out2 = self.layernorm2(attn2 + out1)

        if source_embeddings is not None:
            attn3, attn_weights_block3 = self.mha3(v=source_embeddings, k=source_embeddings, q=out2, mask=None)  # source attention
            attn3 = self.dropout3(attn3, training=training)
            out3 = self.layernorm3(attn3 + out2)
        else:
            attn_weights_block3 = None
            out3 = out2

        ffn_output = self.ffn(out3)
        ffn_output = self.dropout3(ffn_output, training=training)
        out3 = self.layernorm3(ffn_output + out3)

        return out3, attn_weights_block1, attn_weights_block2, attn_weights_block3


class Decoder(tf.keras.layers.Layer):
    def __init__(self, num_layers, d_model, num_heads, dff, target_vocab_size, max_position_encoding, rate=0.1):
        super(Decoder, self).__init__()

        self.d_model = d_model
        self.num_layers = num_layers

        self.embedding = tf.keras.layers.Embedding(target_vocab_size, d_model)
        self.pos_encoding = positional_encoding(max_position_encoding, d_model)

        self.dec_layers = [DecoderLayer(d_model, num_heads, dff, rate) for _ in range(num_layers)]
        self.dropout = tf.keras.layers.Dropout(rate)

    def call(self, x, enc_output, training, look_ahead_mask, padding_mask, source_embeddings, temporal_embeddings):
        seq_len = tf.shape(x)[1]
        attention_weights = {}

        x = self.embedding(x)  # Token embeddings
        x *= tf.math.sqrt(tf.cast(self.d_model, tf.float32))
        x += self.pos_encoding[:, :seq_len, :]  # Positional embeddings
        if source_embeddings is not None:
            x += source_embeddings  # Source embeddings
        if temporal_embeddings is not None:
            x += temporal_embeddings  # Temporal embeddings
        x = self.dropout(x, training=training)

        for i in range(self.num_layers):
            x, block1, block2, block3 = self.dec_layers[i](
                x, enc_output, training=training, look_ahead_mask=look_ahead_mask,
                padding_mask=padding_mask, source_embeddings=source_embeddings)

            attention_weights['decoder_layer{}_block1'.format(i + 1)] = block1
            attention_weights['decoder_layer{}_block2'.format(i + 1)] = block2
            attention_weights['decoder_layer{}_block3'.format(i + 1)] = block3

        return x, attention_weights


class Encoder(tf.keras.layers.Layer):
    def __init__(self, num_layers, d_model, num_heads, dff, input_vocab_size, max_position_encoding, rate=0.1):
        super(Encoder, self).__init__()

        self.d_model = d_model
        self.num_layers = num_layers

        self.embedding = tf.keras.layers.Embedding(input_vocab_size, d_model)
        self.pos_encoding = positional_encoding(max_position_encoding, d_model)

        self.enc_layers = [EncoderLayer(d_model, num_heads, dff, rate) for _ in range(num_layers)]
        self.dropout = tf.keras.layers.Dropout(rate)

    def call(self, x, training, mask, source_embeddings, temporal_embeddings):
        seq_len = tf.shape(x)[1]
        attention_weights = {}

        x = self.embedding(x)  # Token embeddings
        x *= tf.math.sqrt(tf.cast(self.d_model, tf.float32))
        x += self.pos_encoding[:, :seq_len, :]  # Positional embeddings
        if source_embeddings is not None:
            x += source_embeddings  # Source embeddings
        if temporal_embeddings is not None:
            x += temporal_embeddings  # Temporal embeddings
        x = self.dropout(x, training=training)

        for i in range(self.num_layers):
            x, block1, block2 = self.enc_layers[i](x, training=training, mask=mask, source_embeddings=source_embeddings)

            attention_weights['encoder_layer{}_block1'.format(i + 1)] = block1
            attention_weights['encoder_layer{}_block2'.format(i + 1)] = block2

        return x, attention_weights


class DemocraticLLM(tf.keras.Model):
    def __init__(self, num_layers=6, d_model=512, num_heads=8, dff=2048,
                 input_vocab_size=None, target_vocab_size=None, max_position_encoding=256,
                 num_sources=None, temporal_emb=None, dropout_rate=0.1):
        super(DemocraticLLM, self).__init__()

        self.d_model = d_model
        self.encoder = Encoder(num_layers, d_model, num_heads, dff, input_vocab_size, max_position_encoding, dropout_rate)
        self.decoder = Decoder(num_layers, d_model, num_heads, dff, target_vocab_size, max_position_encoding, dropout_rate)

        self.final_layer = tf.keras.layers.Dense(target_vocab_size)

        # One learned embedding per contributing source, and the sinusoidal
        # temporal table built from the dataset's unique timestamps.
        self.source_embedding = tf.keras.layers.Embedding(num_sources, d_model) if num_sources else None
        self.temporal_table = tf.constant(np.asarray(temporal_emb), dtype=tf.float32) if temporal_emb is not None else None

    def call(self, inputs, training=False, enc_padding_mask=None, look_ahead_mask=None,
             dec_padding_mask=None, source_embeddings=None, temporal_embeddings=None):
        # Preserve same-sequence decoding. Full encoder context means this is
        # not qualified as causal next-token prediction; that task choice is open.
        enc_input, source_ids, timestamp_ids = inputs
        dec_input = enc_input

        if enc_padding_mask is None:
            enc_padding_mask = create_padding_mask(enc_input)
        if look_ahead_mask is None:
            look_ahead_mask = create_look_ahead_mask(tf.shape(dec_input)[1])
        if dec_padding_mask is None:
            dec_padding_mask = create_padding_mask(dec_input)
        decoder_self_mask = tf.maximum(look_ahead_mask, dec_padding_mask)

        if source_embeddings is None and self.source_embedding is not None:
            source_embeddings = tf.expand_dims(self.source_embedding(source_ids), 1)  # (batch, 1, d_model)
        if temporal_embeddings is None and self.temporal_table is not None:
            temporal_embeddings = tf.expand_dims(tf.gather(self.temporal_table, timestamp_ids), 1)  # (batch, 1, d_model)

        enc_output, enc_attention_weights = self.encoder(
            enc_input, training=training, mask=enc_padding_mask,
            source_embeddings=source_embeddings, temporal_embeddings=temporal_embeddings)
        dec_output, dec_attention_weights = self.decoder(
            dec_input, enc_output, training=training, look_ahead_mask=decoder_self_mask,
            padding_mask=enc_padding_mask, source_embeddings=source_embeddings,
            temporal_embeddings=temporal_embeddings)

        final_output = self.final_layer(dec_output)
        self.attention_weights = {'encoder': enc_attention_weights, 'decoder': dec_attention_weights}

        return final_output


def main(argv=None):
    """Train the existing sketch with explicit local seed and a preprocessing/weights bundle."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", help="Authorized text,source_id,timestamp CSV")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", required=True, help="Fresh operator-owned private bundle directory")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    # This dedicated training entry point owns framework initialization/shuffling.
    tf.keras.utils.set_random_seed(args.seed)
    prepared = prepare_training_data(load_csv(args.csv), seed=args.seed)
    config = {
        "num_layers": 6, "d_model": 512, "num_heads": 8, "dff": 2048,
        "input_vocab_size": 30000, "target_vocab_size": 30000,
        "max_position_encoding": prepared["max_length"],
        "num_sources": len(prepared["source_map"]) + 1, "dropout_rate": 0.1,
    }
    model = DemocraticLLM(**config, temporal_emb=prepared["temporal"])
    model.compile(loss=masked_token_loss, optimizer="adam", metrics=[MaskedTokenAccuracy()])
    training, validation = prepared["training"], prepared["validation"]
    history = model.fit(
        x=list(training), y=training[0],
        validation_data=(list(validation), validation[0]),
        epochs=10, batch_size=32, verbose=1,
    )
    save_training_bundle(model, prepared, config, args.output_dir)
    return history


if __name__ == "__main__":
    main()
