from keras.applications import VGG16
from keras.models import Model
from keras.layers import Dense, Flatten
from keras.datasets import cifar10
from keras import Input
from keras.optimizers import Adam
from kerassurgeon.operations import delete_channels

from utils import data_generator

import os
import math
import numpy as np

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


class Cifar10VGG16:

    def __init__(self, b=0.5):
        (self.x_train, self.y_train), (self.x_test, self.y_test) = cifar10.load_data()
        self.model = self.__build_model()
        self.num_classes = 10
        self.b = b
        self.action_size = None
        self.state_size = None
        self.epochs = 2
        self.base_model_accuracy = None
        self.action_size = None
        self.state_size = None
        self._current_state = 0
        self.layer_name = None

    def __build_model(self):
        """Builds the VGG16 Model
        """
        input_shape = self.x_train.shape[1:]
        input_tensor = Input(shape=input_shape)
        vgg = VGG16(include_top=False, input_tensor=input_tensor, weights='imagenet')
        flatten = Flatten(name='Flatten')(vgg.output)
        prediction = Dense(10, activation='softmax')(flatten)
        model = Model(input_tensor, prediction)
        model.compile(loss="binary_crossentropy", optimizer=Adam(lr=0.01), metrics=['accuracy'])
        return model

    def get(self, layer_name='block5_conv1'):
        self.layer_name = layer_name
        x = self.model.get_layer(layer_name).get_weights()[0]
        self.state_size, self.action_size = x.shape[:3], x.shape[-1]
        x = x[:, :, :, self._current_state]
        if self._current_state + 1 == self.action_size:
            return True, x
        self._current_state += 1
        return False, x

    def _accuracy_term(self, new_model):
        train_data_generator = data_generator(self.x_train, self.y_train, self.num_classes)
        eval_data_generator = data_generator(self.x_test, self.y_test, self.num_classes)
        train_steps = train_data_generator.n // train_data_generator.batch_size
        validation_steps = eval_data_generator.n // eval_data_generator.batch_size
        new_model.fit_generator(generator=train_data_generator, steps_per_epoch=train_steps, epochs=self.epochs,
                                validation_data=eval_data_generator, validation_steps=validation_steps)

        p_hat = new_model.evaluate_generator(eval_data_generator, eval_data_generator.n, verbose=1)[0]
        if not self.base_model_accuracy:
            print('Calculating the accuracy of the base line model')
            self.base_model_accuracy = self.model.evaluate_generator(eval_data_generator, eval_data_generator.n,
                                                                     verbose=1)[0]
        accuracy_term = (self.b - (self.base_model_accuracy - p_hat)) / self.b
        return accuracy_term

    def step(self, action):
        action = np.where(action[0] == 0)[0]
        new_model = delete_channels(self.model, layer=self.model.get_layer(self.layer_name), channels=action)
        new_model.compile(loss="binary_crossentropy", optimizer=Adam(lr=0.01), metrics=['accuracy'])
        reward = self._accuracy_term(new_model) - math.log10(self.action_size / len(action))
        done, x = self.get()
        return action, reward, done, x