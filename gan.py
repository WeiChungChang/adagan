"""This class implements Generative Adversarial Networks training.

"""

import logging
import tensorflow as tf
import utils
from utils import ProgressBar
import numpy as np
import ops
from metrics import Metrics
from collections import OrderedDict

class Gan(object):
    """A base class for running individual GANs.

    This class announces all the necessary bits for running individual
    GAN trainers. It is assumed that a GAN trainer should receive the
    data points and the corresponding weights, which are used for
    importance sampling of minibatches during the training. All the
    methods should be implemented in the subclasses.
    """
    def __init__(self, opts, data, weights):

        # Create a new session with session.graph = default graph
        self._session = tf.Session()
        self._trained = False
        self._data = data
        self._data_weights = weights
        # Latent noise sampled ones to apply G while training
        self._noise_for_plots = utils.generate_noise(opts, 500)
        # Placeholders
        self._real_points_ph = None
        self._fake_points_ph = None
        self._noise_ph = None


        # Main operations
        self._G = None # Generator function
        self._d_loss = None # Loss of discriminator
        self._g_loss = None # Loss of generator
        self._c_loss = None # Loss of mixture discriminator
        self._c_training = None # Outputs of the mixture discriminator on data

        with self._session.as_default(), self._session.graph.as_default():
            logging.debug('Building the graph...')
            self._build_model_internal(opts)
        # Make sure AdamOptimizer, if used in the Graph, is defined before
        # calling global_variables_initializer().
        try:
            init = tf.global_variables_initializer()
        except:
            init = tf.initialize_all_variables()
        self._session.run(init)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Cleaning the whole default Graph
        logging.debug('Cleaning the graph...')
        tf.reset_default_graph()
        logging.debug('Closing the session...')
        # Finishing the session
        self._session.close()

    def train(self, opts):
        """Train a GAN model.

        """
        with self._session.as_default(), self._session.graph.as_default():
            self._train_internal(opts)
            self._trained = True

    def sample(self, opts, num=100):
        """Sample points from the trained GAN model.

        """
        assert self._trained, 'Can not sample from the un-trained GAN'
        with self._session.as_default(), self._session.graph.as_default():
            return self._sample_internal(opts, num)

    def train_mixture_discriminator(self, opts, fake_images):
        """Train classifier separating true data from points in fake_images.

        """
        with self._session.as_default(), self._session.graph.as_default():
            return self._train_mixture_discriminator_internal(opts, fake_images)

    def _run_batch(self, opts, operation, placeholder, feed,
                   placeholder2=None, feed2=None):
        """Wrapper around session.run to process huge data.

        It is asumed that (a) first dimension of placeholder enumerates
        separate points, and (b) that operation is independently applied
        to every point, i.e. we can split it point-wisely and then merge
        the results. The second placeholder is meant either for is_train
        flag for batch-norm or probabilities of dropout.

        TODO: write util function which will be called both from this method
        and MNIST classification evaluation as well.

        """
        assert len(feed.shape) > 0, 'Empry feed.'
        num_points = feed.shape[0]
        batch_size = opts['tf_run_batch_size']
        batches_num = int(np.ceil((num_points + 0.) / batch_size))
        result = []
        # logging.debug('Running op in batches...')
        # with ProgressBar(opts['verbose'], batches_num) as bar:
        for idx in xrange(batches_num):
            if idx == batches_num - 1:
                if feed2 is None:
                    res = self._session.run(
                        operation,
                        feed_dict={placeholder: feed[idx * batch_size:]})
                else:
                    res = self._session.run(
                        operation,
                        feed_dict={placeholder: feed[idx * batch_size:],
                                   placeholder2: feed2})
            else:
                if feed2 is None:
                    res = self._session.run(
                        operation,
                        feed_dict={placeholder: feed[idx * batch_size:
                                                     (idx + 1) * batch_size]})
                else:
                    res = self._session.run(
                        operation,
                        feed_dict={placeholder: feed[idx * batch_size:
                                                     (idx + 1) * batch_size],
                                   placeholder2: feed2})

            if len(res.shape) == 1:
                # convert (n,) vector to (n,1) array
                res = np.reshape(res, [-1, 1])
            result.append(res)
        #         bar.bam()
        result = np.vstack(result)
        assert len(result) == num_points
        return result

    def _build_model_internal(self, opts):
        """Build a TensorFlow graph with all the necessary ops.

        """
        assert False, 'Gan base class has no build_model method defined.'

    def _train_internal(self, opts):
        assert False, 'Gan base class has no train method defined.'

    def _sample_internal(self, opts, num):
        assert False, 'Gan base class has no sample method defined.'

    def _train_mixture_discriminator_internal(self, opts, fake_images):
        assert False, 'Gan base class has no mixture discriminator method defined.'

class ToyGan(Gan):
    """A simple GAN implementation, suitable for toy datasets.

    """

    def generator(self, opts, noise, reuse=False):
        """Generator function, suitable for simple toy experiments.

        Args:
            noise: [num_points, dim] array, where dim is dimensionality of the
                latent noise space.
        Returns:
            [num_points, dim1, dim2, dim3] array, where the first coordinate
            indexes the points, which all are of the shape (dim1, dim2, dim3).
        """
        output_shape = self._data.data_shape

        with tf.variable_scope("GENERATOR", reuse=reuse):
            h0 = ops.linear(opts, noise, 10, 'h0_lin')
            h0 = tf.nn.relu(h0)
            h1 = ops.linear(opts, h0, 5, 'h1_lin')
            h1 = tf.nn.relu(h1)
            h2 = ops.linear(opts, h1, np.prod(output_shape), 'h2_lin')
            h2 = tf.reshape(h2, [-1] + list(output_shape))

        return h2

    def discriminator(self, opts, input_,
                      prefix='DISCRIMINATOR', reuse=False):
        """Discriminator function, suitable for simple toy experiments.

        """
        shape = input_.get_shape().as_list()
        assert len(shape) > 0, 'No inputs to discriminate.'

        with tf.variable_scope(prefix, reuse=reuse):
            h0 = ops.linear(opts, input_, 50, 'h0_lin')
            h0 = tf.nn.relu(h0)
            h1 = ops.linear(opts, h0, 30, 'h1_lin')
            h1 = tf.nn.relu(h1)
            h2 = ops.linear(opts, h1, 1, 'h2_lin')

        return h2

    def _build_model_internal(self, opts):
        """Build the Graph corresponding to GAN implementation.

        """
        data_shape = self._data.data_shape

        # Placeholders
        real_points_ph = tf.placeholder(
            tf.float32, [None] + list(data_shape), name='real_points')
        fake_points_ph = tf.placeholder(
            tf.float32, [None] + list(data_shape), name='fake_points')
        noise_ph = tf.placeholder(
            tf.float32, [None] + [opts['latent_space_dim']], name='noise')

        # Operations
        G = self.generator(opts, noise_ph)

        d_logits_real = self.discriminator(opts, real_points_ph)
        d_logits_fake = self.discriminator(opts, G, reuse=True)

        c_logits_real = self.discriminator(
            opts, real_points_ph, prefix='CLASSIFIER')
        c_logits_fake = self.discriminator(
            opts, fake_points_ph, prefix='CLASSIFIER', reuse=True)
        c_training = tf.nn.sigmoid(
            self.discriminator(opts, real_points_ph, prefix='CLASSIFIER', reuse=True))

        d_loss_real = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                d_logits_real, tf.ones_like(d_logits_real)))
        d_loss_fake = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                d_logits_fake, tf.zeros_like(d_logits_fake)))
        d_loss = d_loss_real + d_loss_fake

        g_loss = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                d_logits_fake, tf.ones_like(d_logits_fake)))

        c_loss_real = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                c_logits_real, tf.ones_like(c_logits_real)))
        c_loss_fake = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                c_logits_fake, tf.zeros_like(c_logits_fake)))
        c_loss = c_loss_real + c_loss_fake

        t_vars = tf.trainable_variables()
        d_vars = [var for var in t_vars if 'DISCRIMINATOR/' in var.name]
        g_vars = [var for var in t_vars if 'GENERATOR/' in var.name]
        d_optim = ops.optimizer(opts, 'd').minimize(d_loss, var_list=d_vars)
        g_optim = ops.optimizer(opts, 'g').minimize(g_loss, var_list=g_vars)
        c_vars = [var for var in t_vars if 'CLASSIFIER/' in var.name]
        c_optim = ops.optimizer(opts).minimize(c_loss, var_list=c_vars)

        self._real_points_ph = real_points_ph
        self._fake_points_ph = fake_points_ph
        self._noise_ph = noise_ph

        self._G = G
        self._d_loss = d_loss
        self._g_loss = g_loss
        self._c_loss = c_loss
        self._c_training = c_training
        self._g_optim = g_optim
        self._d_optim = d_optim
        self._c_optim = c_optim


    def _train_internal(self, opts):
        """Train a GAN model.

        """

        batches_num = self._data.num_points / opts['batch_size']
        train_size = self._data.num_points

        counter = 0
        logging.debug('Training GAN')
        with ProgressBar(opts['verbose'], opts['gan_epoch_num']) as pbar:
            for _epoch in xrange(opts["gan_epoch_num"]):
                for _idx in xrange(batches_num):
                    data_ids = np.random.choice(train_size, opts['batch_size'],
                                                replace=False, p=self._data_weights)
                    batch_images = self._data.data[data_ids].astype(np.float)
                    batch_noise = utils.generate_noise(opts, opts['batch_size'])
                    # Update discriminator parameters
                    for _iter in xrange(opts['d_steps']):
                        _ = self._session.run(
                            self._d_optim,
                            feed_dict={self._real_points_ph: batch_images,
                                       self._noise_ph: batch_noise})
                    # Update generator parameters
                    for _iter in xrange(opts['g_steps']):
                        _ = self._session.run(
                            self._g_optim, feed_dict={self._noise_ph: batch_noise})
                    counter += 1
                    if opts['verbose'] and counter % 100 == 0:
                        metrics = Metrics()
                        points_to_plot = self._run_batch(
                            opts, self._G, self._noise_ph,
                            self._noise_for_plots[0:300])
                        metrics.make_plots(
                            opts,
                            counter,
                            self._data.data[0:300],
                            points_to_plot,
                            prefix='gan_e%d_mb%d_' % (_epoch, _idx))
                pbar.bam()



    def _sample_internal(self, opts, num):
        """Sample from the trained GAN model.

        """
        noise = utils.generate_noise(opts, num)
        sample = self._run_batch(opts, self._G, self._noise_ph, noise)
        # sample = self._session.run(
        #     self._G, feed_dict={self._noise_ph: noise})
        return sample

    def _train_mixture_discriminator_internal(self, opts, fake_images):
        """Train a classifier separating true data from points in fake_images.

        """

        batches_num = self._data.num_points / opts['batch_size']
        logging.debug('Training a mixture discriminator')
        with ProgressBar(opts['verbose'], opts['mixture_c_epoch_num']) as pbar:
            for epoch in xrange(opts["mixture_c_epoch_num"]):
                for idx in xrange(batches_num):
                    ids = np.random.choice(len(fake_images), opts['batch_size'],
                                           replace=False)
                    batch_fake_images = fake_images[ids]
                    ids = np.random.choice(self._data.num_points, opts['batch_size'],
                                           replace=False)
                    batch_real_images = self._data.data[ids]
                    _ = self._session.run(
                        self._c_optim,
                        feed_dict={self._real_points_ph: batch_real_images,
                                   self._fake_points_ph: batch_fake_images})
                pbar.bam()

        res = self._run_batch(
            opts, self._c_training,
            self._real_points_ph, self._data.data)
        return res

class ImageGan(Gan):
    """A simple GAN implementation, suitable for pictures.

    """

    def __init__(self, opts, data, weights):

        # One more placeholder for batch norm
        self._is_training_ph = None

        Gan.__init__(self, opts, data, weights)

    def generator(self, opts, noise, is_training, reuse=False):
        """Generator function, suitable for simple picture experiments.

        Args:
            noise: [num_points, dim] array, where dim is dimensionality of the
                latent noise space.
            is_training: bool, defines whether to use batch_norm in the train
                or test mode.
        Returns:
            [num_points, dim1, dim2, dim3] array, where the first coordinate
            indexes the points, which all are of the shape (dim1, dim2, dim3).
        """

        output_shape = self._data.data_shape # (dim1, dim2, dim3)
        # Computing the number of noise vectors on-the-go
        dim1 = tf.shape(noise)[0]
        num_filters = opts['g_num_filters']

        with tf.variable_scope("GENERATOR", reuse=reuse):

            height = output_shape[0] / 4
            width = output_shape[1] / 4
            h0 = ops.linear(opts, noise, num_filters * height * width,
                            scope='h0_lin')
            h0 = tf.reshape(h0, [-1, height, width, num_filters])
            h0 = ops.batch_norm(opts, h0, is_training, reuse, scope='bn_layer1')
            # h0 = tf.nn.relu(h0)
            h0 = ops.lrelu(h0)
            _out_shape = [dim1, height * 2, width * 2, num_filters / 2]
            # for 28 x 28 does 7 x 7 --> 14 x 14
            h1 = ops.deconv2d(opts, h0, _out_shape, scope='h1_deconv')
            h1 = ops.batch_norm(opts, h1, is_training, reuse, scope='bn_layer2')
            # h1 = tf.nn.relu(h1)
            h1 = ops.lrelu(h1)
            _out_shape = [dim1, height * 4, width * 4, num_filters / 4]
            # for 28 x 28 does 14 x 14 --> 28 x 28 
            h2 = ops.deconv2d(opts, h1, _out_shape, scope='h2_deconv')
            h2 = ops.batch_norm(opts, h2, is_training, reuse, scope='bn_layer3')
            # h2 = tf.nn.relu(h2)
            h2 = ops.lrelu(h2)
            _out_shape = [dim1] + list(output_shape)
            # data_shape[0] x data_shape[1] x ? -> data_shape
            h3 = ops.deconv2d(opts, h2, _out_shape,
                              d_h=1, d_w=1, scope='h3_deconv')
            h3 = ops.batch_norm(opts, h3, is_training, reuse, scope='bn_layer4')

        if opts['input_normalize_sym']:
            return tf.nn.tanh(h3)
        else:
            return tf.nn.sigmoid(h3)

    def discriminator(self, opts, input_, is_training,
                      prefix='DISCRIMINATOR', reuse=False):
        """Discriminator function, suitable for simple toy experiments.

        """
        shape = input_.get_shape().as_list()
        assert len(shape) > 0, 'No inputs to discriminate.'
        num_filters = opts['d_num_filters']

        with tf.variable_scope(prefix, reuse=reuse):
            h0 = ops.conv2d(opts, input_, num_filters, scope='h0_conv')
            h0 = ops.batch_norm(opts, h0, is_training, reuse, scope='bn_layer1')
            h0 = ops.lrelu(h0)
            h1 = ops.conv2d(opts, h0, num_filters * 2, scope='h1_conv')
            h1 = ops.batch_norm(opts, h1, is_training, reuse, scope='bn_layer2')
            h1 = ops.lrelu(h1)
            h2 = ops.conv2d(opts, h1, num_filters * 4, scope='h2_conv')
            h2 = ops.batch_norm(opts, h2, is_training, reuse, scope='bn_layer3')
            h2 = ops.lrelu(h2)
            h3 = ops.linear(opts, h2, 1, scope='h3_lin')

        return h3

    def _build_model_internal(self, opts):
        """Build the Graph corresponding to GAN implementation.

        """
        data_shape = self._data.data_shape

        # Placeholders
        real_points_ph = tf.placeholder(
            tf.float32, [None] + list(data_shape), name='real_points')
        fake_points_ph = tf.placeholder(
            tf.float32, [None] + list(data_shape), name='fake_points')
        noise_ph = tf.placeholder(
            tf.float32, [None] + [opts['latent_space_dim']], name='noise')
        is_training_ph = tf.placeholder(tf.bool, name='is_train')


        # Operations
        G = self.generator(opts, noise_ph, is_training_ph)
        # We use conv2d_transpose in the generator, which results in the
        # output tensor of undefined shapes. However, we statically know
        # the shape of the generator output, which is [-1, dim1, dim2, dim3]
        # where (dim1, dim2, dim3) is given by self._data.data_shape
        G.set_shape([None] + list(self._data.data_shape))

        d_logits_real = self.discriminator(opts, real_points_ph, is_training_ph)
        d_logits_fake = self.discriminator(opts, G, is_training_ph, reuse=True)

        c_logits_real = self.discriminator(
            opts, real_points_ph, is_training_ph, prefix='CLASSIFIER')
        c_logits_fake = self.discriminator(
            opts, fake_points_ph, is_training_ph, prefix='CLASSIFIER', reuse=True)
        c_training = tf.nn.sigmoid(
            self.discriminator(opts, real_points_ph, is_training_ph,
                               prefix='CLASSIFIER', reuse=True))

        d_loss_real = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                d_logits_real, tf.ones_like(d_logits_real)))
        d_loss_fake = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                d_logits_fake, tf.zeros_like(d_logits_fake)))
        d_loss = d_loss_real + d_loss_fake

        g_loss = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                d_logits_fake, tf.ones_like(d_logits_fake)))

        c_loss_real = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                c_logits_real, tf.ones_like(c_logits_real)))
        c_loss_fake = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                c_logits_fake, tf.zeros_like(c_logits_fake)))
        c_loss = c_loss_real + c_loss_fake

        t_vars = tf.trainable_variables()
        d_vars = [var for var in t_vars if 'DISCRIMINATOR/' in var.name]
        g_vars = [var for var in t_vars if 'GENERATOR/' in var.name]

        d_optim = ops.optimizer(opts, 'd').minimize(d_loss, var_list=d_vars)
        g_optim = ops.optimizer(opts, 'g').minimize(g_loss, var_list=g_vars)

        # d_optim_op = ops.optimizer(opts, 'd')
        # g_optim_op = ops.optimizer(opts, 'g')

        # def debug_grads(grad, var):
        #     _grad =  tf.Print(
        #         grad, # grads_and_vars,
        #         [tf.global_norm([grad])], # tf.global_norm([grad for (grad, var) in grads_and_vars]).get_shape(),
        #         'Global grad norm of %s: ' % var.name)
        #     return _grad, var

        # d_grads_and_vars = [debug_grads(grad, var) for (grad, var) in \
        #     d_optim_op.compute_gradients(d_loss, var_list=d_vars)]
        # g_grads_and_vars = [debug_grads(grad, var) for (grad, var) in \
        #     g_optim_op.compute_gradients(g_loss, var_list=g_vars)]
        # d_optim = d_optim_op.apply_gradients(d_grads_and_vars)
        # g_optim = g_optim_op.apply_gradients(g_grads_and_vars)

        c_vars = [var for var in t_vars if 'CLASSIFIER/' in var.name]
        c_optim = ops.optimizer(opts).minimize(c_loss, var_list=c_vars)

        self._real_points_ph = real_points_ph
        self._fake_points_ph = fake_points_ph
        self._noise_ph = noise_ph
        self._is_training_ph = is_training_ph
        self._G = G
        self._d_loss = d_loss
        self._g_loss = g_loss
        self._c_loss = c_loss
        self._c_training = c_training
        self._g_optim = g_optim
        self._d_optim = d_optim
        self._c_optim = c_optim

        logging.debug("Building Graph Done.")


    def _train_internal(self, opts):
        """Train a GAN model.

        """

        batches_num = self._data.num_points / opts['batch_size']
        train_size = self._data.num_points

        counter = 0
        logging.debug('Training GAN')
        with ProgressBar(opts['verbose'], opts['gan_epoch_num']) as pbar:
            for _epoch in xrange(opts["gan_epoch_num"]):
                for _idx in xrange(batches_num):
                    # logging.debug('Step %d of %d' % (_idx, batches_num ) )
                    data_ids = np.random.choice(train_size, opts['batch_size'],
                                                replace=False, p=self._data_weights)
                    batch_images = self._data.data[data_ids].astype(np.float)
                    batch_noise = utils.generate_noise(opts, opts['batch_size'])
                    # Update discriminator parameters
                    for _iter in xrange(opts['d_steps']):
                        _ = self._session.run(
                            self._d_optim,
                            feed_dict={self._real_points_ph: batch_images,
                                       self._noise_ph: batch_noise,
                                       self._is_training_ph: True})
                    # Update generator parameters
                    for _iter in xrange(opts['g_steps']):
                        _ = self._session.run(
                            self._g_optim,
                            feed_dict={self._noise_ph: batch_noise,
                            self._is_training_ph: True})
                    counter += 1

                    if opts['verbose'] and counter % opts['plot_every'] == 0:
                        logging.debug(
                            'Epoch: %d/%d, batch:%d/%d' % \
                            (_epoch, opts['gan_epoch_num'], _idx, batches_num))
                        metrics = Metrics()
                        points_to_plot = self._run_batch(
                            opts, self._G, self._noise_ph,
                            self._noise_for_plots[0:16],
                            self._is_training_ph, False)
                        metrics.make_plots(
                            opts,
                            counter,
                            None,
                            points_to_plot,
                            prefix='sample_e%02d_mb%05d_' % (_epoch, _idx))
                    if opts['early_stop'] > 0 and counter > opts['early_stop']:
                        break
                pbar.bam()



    def _sample_internal(self, opts, num):
        """Sample from the trained GAN model.

        """
        noise = utils.generate_noise(opts, num)
        sample = self._run_batch(
            opts, self._G, self._noise_ph, noise,
            self._is_training_ph, False)
        # sample = self._session.run(
        #     self._G, feed_dict={self._noise_ph: noise})
        return sample

    def _train_mixture_discriminator_internal(self, opts, fake_images):
        """Train a classifier separating true data from points in fake_images.

        """

        batches_num = self._data.num_points / opts['batch_size']
        logging.debug('Training a mixture discriminator')
        with ProgressBar(opts['verbose'], opts['mixture_c_epoch_num']) as pbar:
            for epoch in xrange(opts["mixture_c_epoch_num"]):
                for idx in xrange(batches_num):
                    ids = np.random.choice(len(fake_images), opts['batch_size'],
                                           replace=False)
                    batch_fake_images = fake_images[ids]
                    ids = np.random.choice(self._data.num_points, opts['batch_size'],
                                           replace=False)
                    batch_real_images = self._data.data[ids]
                    _ = self._session.run(
                        self._c_optim,
                        feed_dict={self._real_points_ph: batch_real_images,
                                   self._fake_points_ph: batch_fake_images,
                                   self._is_training_ph: True})
                pbar.bam()

        res = self._run_batch(
            opts, self._c_training,
            self._real_points_ph, self._data.data,
            self._is_training_ph, False)
        return res

class UnrolledGan(ImageGan):

### Generator and Discriminator without batch_norm ####
#     def generator(self, opts, noise, is_training, reuse=False):
#         """Generator function, suitable for simple picture experiments.
# 
#         Args:
#             noise: [num_points, dim] array, where dim is dimensionality of the
#                 latent noise space.
#             is_training: bool, defines whether to use batch_norm in the train
#                 or test mode.
#         Returns:
#             [num_points, dim1, dim2, dim3] array, where the first coordinate
#             indexes the points, which all are of the shape (dim1, dim2, dim3).
#         """
# 
#         output_shape = self._data.data_shape # (dim1, dim2, dim3)
#         # Computing the number of noise vectors on-the-go
#         dim1 = tf.shape(noise)[0]
#         num_filters = opts['g_num_filters']
# 
#         with tf.variable_scope("GENERATOR", reuse=reuse):
# 
#             height = output_shape[0] / 4
#             width = output_shape[1] / 4
#             h0 = ops.linear(opts, noise, num_filters * height * width,
#                             scope='h0_lin')
#             h0 = tf.reshape(h0, [-1, height, width, num_filters])
#             h0 = tf.nn.relu(h0)
#             _out_shape = [dim1, height * 2, width * 2, num_filters / 2]
#             # for 28 x 28 does 7 x 7 --> 14 x 14
#             h1 = ops.deconv2d(opts, h0, _out_shape, scope='h1_deconv')
#             h1 = tf.nn.relu(h1)
#             _out_shape = [dim1, height * 4, width * 4, num_filters / 4]
#             # for 28 x 28 does 14 x 14 --> 28 x 28 
#             h2 = ops.deconv2d(opts, h1, _out_shape, scope='h2_deconv')
#             h2 = tf.nn.relu(h2)
#             _out_shape = [dim1] + list(output_shape)
#             # data_shape[0] x data_shape[1] x ? -> data_shape
#             h3 = ops.deconv2d(opts, h2, _out_shape,
#                               d_h=1, d_w=1, scope='h3_deconv')
# 
#         return tf.nn.sigmoid(h3)
# 
#     def discriminator(self, opts, input_, is_training,
#                       prefix='DISCRIMINATOR', reuse=False):
#         """Discriminator function, suitable for simple toy experiments.
# 
#         """
#         shape = input_.get_shape().as_list()
#         assert len(shape) > 0, 'No inputs to discriminate.'
#         num_filters = opts['d_num_filters']
# 
#         with tf.variable_scope(prefix, reuse=reuse):
#             h0 = ops.conv2d(opts, input_, num_filters, scope='h0_conv')
#             h0 = ops.lrelu(h0)
#             h1 = ops.conv2d(opts, h0, num_filters * 2, scope='h1_conv')
#             h1 = ops.lrelu(h1)
#             h2 = ops.conv2d(opts, h1, num_filters * 4, scope='h2_conv')
#             h2 = ops.lrelu(h2)
#             h3 = ops.linear(opts, h2, 1, scope='h3_lin')
# 
#         return h3

    def _build_model_internal(self, opts):
        """Build the Graph corresponding to GAN implementation.

        """
        from keras.optimizers import Adam

        ds = tf.contrib.distributions
        slim = tf.contrib.slim
        graph_replace = tf.contrib.graph_editor.graph_replace

        data_shape = self._data.data_shape

        # Placeholders
        real_points_ph = tf.placeholder(
            tf.float32, [None] + list(data_shape), name='real_points')
        fake_points_ph = tf.placeholder(
            tf.float32, [None] + list(data_shape), name='fake_points')
        noise_ph = tf.placeholder(
            tf.float32, [None] + [opts['latent_space_dim']], name='noise')
        # is_training_ph = tf.placeholder(tf.bool, name='is_train')
        is_training_ph = True


        # Operations
        G = self.generator(opts, noise_ph, is_training_ph)
        # We use conv2d_transpose in the generator, which results in the
        # output tensor of undefined shapes. However, we statically know
        # the shape of the generator output, which is [-1, dim1, dim2, dim3]
        # where (dim1, dim2, dim3) is given by self._data.data_shape
        G.set_shape([None] + list(self._data.data_shape))

        d_logits_real = self.discriminator(opts, real_points_ph, is_training_ph)
        d_logits_fake = self.discriminator(opts, G, is_training_ph, reuse=True)

        c_logits_real = self.discriminator(
            opts, real_points_ph, is_training_ph, prefix='CLASSIFIER')
        c_logits_fake = self.discriminator(
            opts, fake_points_ph, is_training_ph, prefix='CLASSIFIER', reuse=True)
        c_training = tf.nn.sigmoid(
            self.discriminator(opts, real_points_ph, is_training_ph,
                               prefix='CLASSIFIER', reuse=True))

        d_loss_real = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                d_logits_real, tf.ones_like(d_logits_real)))
        d_loss_fake = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                d_logits_fake, tf.zeros_like(d_logits_fake)))
        d_loss = d_loss_real + d_loss_fake

        c_loss_real = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                c_logits_real, tf.ones_like(c_logits_real)))
        c_loss_fake = tf.reduce_mean(
            tf.nn.sigmoid_cross_entropy_with_logits(
                c_logits_fake, tf.zeros_like(c_logits_fake)))
        c_loss = c_loss_real + c_loss_fake

        t_vars = tf.trainable_variables()
        d_vars = [var for var in t_vars if 'DISCRIMINATOR/' in var.name]
        c_vars = [var for var in t_vars if 'CLASSIFIER/' in var.name]
        g_vars = [var for var in t_vars if 'GENERATOR/' in var.name]

        # Vanilla discriminator update
        d_opt = Adam(lr=opts['opt_learning_rate'],
                     beta_1=opts['opt_beta1'],
                     epsilon=1e-8) ## UnrolledGAN keep it a param 
        updates = d_opt.get_updates(d_vars, [], d_loss)
        d_optim = tf.group(*updates, name="d_optim")

        # Vanilla classifier update
        c_optim = ops.optimizer(opts).minimize(c_loss, var_list=c_vars)

        # Unroll optimization of the discrimiantor
        if opts['unrolling_steps'] > 0:
            # Get dictionary mapping from variables to their
            # update value after one optimization step
            update_dict = self.extract_update_dict(updates)
            cur_update_dict = update_dict
            for i in xrange(opts['unrolling_steps'] - 1):
                # Compute variable updates given the
                # previous iteration's updated variable
                cur_update_dict = graph_replace(update_dict, cur_update_dict)
            # Final unrolled loss uses the parameters at the last time step
            g_loss = -graph_replace(d_loss, cur_update_dict)
        else:
            g_loss = -d_loss

        # Optimize the generator on the unrolled loss
        g_optim = ops.optimizer(opts).minimize(g_loss, var_list=g_vars)

        self._real_points_ph = real_points_ph
        self._fake_points_ph = fake_points_ph
        self._noise_ph = noise_ph
        self._is_training_ph = is_training_ph
        self._G = G
        self._d_loss = d_loss
        self._g_loss = g_loss
        self._c_loss = c_loss
        self._c_training = c_training
        self._g_optim = g_optim
        self._d_optim = d_optim
        self._c_optim = c_optim

    def extract_update_dict(self,update_ops):
        ### From Unrolled GAN demo ### 
        """Extract variables and their new values from Assign and AssignAdd ops.

        Args:
            update_ops: list of Assign and AssignAdd ops, typically computed using Keras' opt.get_updates()

        Returns:
            dict mapping from variable values to their updated value
        """
        name_to_var = {v.name: v for v in tf.global_variables()}
        updates = OrderedDict()
        for update in update_ops:
            var_name = update.op.inputs[0].name
            var = name_to_var[var_name]
            value = update.op.inputs[1]
            if update.op.type == 'Assign':
                updates[var.value()] = value
            elif update.op.type == 'AssignAdd':
                updates[var.value()] = var + value
            else:
                raise ValueError("Update op type (%s) must be of type Assign or AssignAdd"%update_op.op.type)
        return updates

    def _train_internal(self, opts):
        """Train a GAN model.

        """

        batches_num = self._data.num_points / opts['batch_size']
        train_size = self._data.num_points

        counter = 0
        logging.debug('Training GAN')
        with ProgressBar(opts['verbose'], opts['gan_epoch_num']) as pbar:
            for _epoch in xrange(opts["gan_epoch_num"]):
                for _idx in xrange(batches_num):
                    # logging.debug('Step %d of %d' % (_idx, batches_num ) )
                    data_ids = np.random.choice(train_size, opts['batch_size'],
                                                replace=False, p=self._data_weights)
                    batch_images = self._data.data[data_ids].astype(np.float)
                    batch_noise = utils.generate_noise(opts, opts['batch_size'])
                    # Update discriminator parameters
                    for _iter in xrange(opts['d_steps']):
                        _ = self._session.run(
                            self._d_optim,
                            feed_dict={self._real_points_ph: batch_images,
                                       self._noise_ph: batch_noise}) # add is_training placeh.
                    # Update generator parameters
                    for _iter in xrange(opts['g_steps']):
                        _ = self._session.run(
                            self._g_optim,
                            feed_dict={self._real_points_ph: batch_images,
                            self._noise_ph: batch_noise}) # add is_training placeh.
                    counter += 1

                    if opts['verbose'] and counter % opts['plot_every'] == 0:
                        logging.debug(
                            'Epoch: %d/%d, batch:%d/%d' % \
                            (_epoch, opts['gan_epoch_num'], _idx, batches_num))
                        metrics = Metrics()
                        points_to_plot = self._run_batch(
                            opts, self._G, self._noise_ph,
                            self._noise_for_plots[0:16])
                            # add is_training placeh.
                        metrics.make_plots(
                            opts,
                            counter,
                            None,
                            points_to_plot,
                            prefix='sample_e%02d_mb%05d_' % (_epoch, _idx))
                    if opts['early_stop'] > 0 and counter > opts['early_stop']:
                        break
                pbar.bam()

## SUPPRESS THIS PART ONCE is_training becomes a placeholder ####
    def _sample_internal(self, opts, num):
        """Sample from the trained GAN model.

        """
        noise = utils.generate_noise(opts, num)
        sample = self._run_batch(
            opts, self._G, self._noise_ph, noise)
        #     self._is_training_ph, False)
        # sample = self._session.run(
        #     self._G, feed_dict={self._noise_ph: noise})
        return sample

    def _train_mixture_discriminator_internal(self, opts, fake_images):
        """Train a classifier separating true data from points in fake_images.

        """

        batches_num = self._data.num_points / opts['batch_size']
        logging.debug('Training a mixture discriminator')
        with ProgressBar(opts['verbose'], opts['mixture_c_epoch_num']) as pbar:
            for epoch in xrange(opts["mixture_c_epoch_num"]):
                for idx in xrange(batches_num):
                    ids = np.random.choice(len(fake_images), opts['batch_size'],
                                           replace=False)
                    batch_fake_images = fake_images[ids]
                    ids = np.random.choice(self._data.num_points, opts['batch_size'],
                                           replace=False)
                    batch_real_images = self._data.data[ids]
                    _ = self._session.run(
                        self._c_optim,
                        feed_dict={self._real_points_ph: batch_real_images,
                                   self._fake_points_ph: batch_fake_images})
                                   # self._is_training_ph: True})
                pbar.bam()

        res = self._run_batch(
            opts, self._c_training,
            self._real_points_ph, self._data.data,
            self._is_training_ph, False)
        return res

