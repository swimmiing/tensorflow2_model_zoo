"""Example program training/inference on digit recognition problem with tensorflow 2.0."""
import argparse
import cv2
import os
import tensorflow as tf
from tensorflow import keras
from datetime import datetime

# The model here is Multilayer peceptron/Fully connected network with 2 hidden layers.
# The encoder/feature_extraction part is (Linear -> BN -> Relu) * 2
# The decoder/classifier part is Linear -> Dropout -> Softmax
# It gets to 95% + test accuracy in 1 epoch.
# the training loop is in pytorch style with eager execution only.
# For Subclassed model like this one, it seems we can not use SavedModel util from tf2.0
# We can only save the weights, the python code is needed to re-construct model to be used for inference

BATCH_SIZE = 32
NUM_CLASS = 10
NUM_EPOCHS = 5
LEARNING_RATE = 1e-3
if not os.path.exists('models/mnist_mlp_eager/'):
    os.mkdir('models/mnist_mlp_eager/')
MODEL_FILE = 'models/mnist_mlp_eager/model'


class MLP(keras.Model):
    """MLP model class using tf.Keras API."""
    def __init__(self, num_class=NUM_CLASS):
        super(MLP, self).__init__()
        self.encoder = keras.Sequential([
            keras.layers.Dense(units=128),
            keras.layers.BatchNormalization(),
            keras.layers.Activation(activation='relu'),
            keras.layers.Dense(units=32),
            keras.layers.BatchNormalization(),
            keras.layers.Activation(activation='relu')
        ])
        self.decoder = keras.Sequential([
            keras.layers.Dense(units=num_class),
            keras.layers.Dropout(rate=.1),
            keras.layers.Activation(activation='softmax')
        ])

    def call(self, x, training=True):
        x = self.encoder(x, training=training)
        x = self.decoder(x, training=training)
        return x


def train(verbose=0):
    """Train the model."""
    # load dataset
    mnist = keras.datasets.mnist
    (x_train, y_train), (x_valid, y_valid) = mnist.load_data()
    x_train = x_train.reshape(60000, 784).astype('float32') / 255.0
    x_valid = x_valid.reshape(10000, 784).astype('float32') / 255.0
    train_dataset = tf.data.Dataset.from_tensor_slices((x_train, y_train)).batch(BATCH_SIZE)
    valid_dataset = tf.data.Dataset.from_tensor_slices((x_valid, y_valid)).batch(BATCH_SIZE)

    # config model
    model = MLP()
    criterion = keras.losses.SparseCategoricalCrossentropy()
    optimizer = keras.optimizers.Adam(learning_rate=LEARNING_RATE)
    train_loss = keras.metrics.Mean()
    train_accuracy = keras.metrics.SparseCategoricalAccuracy()
    test_loss = keras.metrics.Mean()
    test_accuracy = keras.metrics.SparseCategoricalAccuracy()

    # training loop
    for epoch in range(NUM_EPOCHS):
        t0 = datetime.now()
        # train
        train_loss.reset_states()
        train_accuracy.reset_states()
        for idx, (x_batch, y_batch) in enumerate(train_dataset):
            with tf.GradientTape() as tape:
                out = model(x_batch, training=True)
                loss = criterion(y_batch, out)
            grad = tape.gradient(loss, model.trainable_variables)
            optimizer.apply_gradients(zip(grad, model.trainable_variables))
            train_loss(loss)
            train_accuracy(y_batch, out)

        # validate
        test_loss.reset_states()
        test_accuracy.reset_states()
        for idx, (x_batch, y_batch) in enumerate(valid_dataset):
            out = model(x_batch, training=False)
            loss = criterion(y_batch, out)
            test_loss(loss)
            test_accuracy(y_batch, out)

        message_template = 'epoch {:>3} time {} sec / epoch train cce {:.4f} acc {:4.2f}% test cce {:.4f} acc {:4.2f}%'
        t1 = datetime.now()
        if verbose:
            print(message_template.format(
                epoch + 1, (t1 - t0).seconds,
                train_loss.result(), train_accuracy.result() * 100,
                test_loss.result(), test_accuracy.result() * 100
            ))
    # it appears that for keras.Model subclass model, we can only save weights in 2.0 alpha
    model.save_weights(MODEL_FILE, save_format='tf')


def inference(filepath):
    """Reconstruct the model, load weights and run inference on a given picture."""
    model = MLP()
    model.load_weights(MODEL_FILE)
    image = cv2.imread(filepath, 0).reshape(1, 784).astype('float32') / 255
    probs = model.predict(image)
    print('it is a: {} with probability {:4.2f}%'.format(probs.argmax(), 100 * probs.max()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='parameters for program')
    parser.add_argument('procedure', choices=['train', 'inference'],
                        help='Whether to train a new model or use trained model to inference.')
    parser.add_argument('--image_path', default=None, help='Path to jpeg image file to predict on.')
    parser.add_argument('--gpu', default='', help='gpu device id expose to program, default is cpu only.')
    parser.add_argument('--verbose', type=int, default=0)
    args = parser.parse_args()

    os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu

    if args.procedure == 'train':
        train(args.verbose)
    else:
        assert os.path.exists(MODEL_FILE + '.index'), 'model not found, train a model before calling inference.'
        assert os.path.exists(args.image_path), 'can not find image file.'
        inference(args.image_path)
