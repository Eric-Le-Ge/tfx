# CIFAR-10 Transfer Learning and MLKit integration Example with Distributed Training

This example illustrates how to modify the base example for distributed training with a distributed node pool on Google Kubernetes Engine (GKE).

## Instructions

### Set Up a Node Pool
The guide assumes that you have command line access to `kubectl`.
If you do not have access to a GKE cluster, follow the quickstart guide [here](https://cloud.google.com/kubernetes-engine/docs/quickstart) to start one.

Then, follow the instructions below for how to set up a node pool on GKE:
https://cloud.google.com/kubernetes-engine/docs/how-to/node-pools

If you wish to use GPUs in your training, follow the instructions here:
https://cloud.google.com/kubernetes-engine/docs/how-to/gpus

**Important:** In order to have write access to the GCS buckets in the project, you need to set up the node pool to have full service account scope access. If you are using the console, you can go to
Security -> Access scopes and select "Allow full access to all Cloud APIs". If you are using gcloud,
you configure this with the `--scopes` flag.

### Set Up a Custom Image for Training (Optional)
The base CIFAR10 example relies on dependencies including TensorFlowJS that do not come with the default TFX installation. 
If you do not wish to use a custom Docker image, you can remove the TFLite model rewriting portion in `cifar10_utils_native_keras`.

Start from a base TensorFlow GPU image in your Dockerfile:

```
FROM tensorflow/tensorflow:latest-gpu
```

Then, follow the instructions in the base example to configure your training environment. For the example dataset to work, you would need ro run the following commands:
```
RUN git clone https://github.com/tensorflow/tfx ~/tfx-source && \
    pushd ~/tfx-source && \
    cp -r ~/tfx-source/tfx/examples/cifar10 ~/
RUN pip install -e cifar10/
```

Finally, build and upload the new image to your container registry:
```
docker build -t $YOUR_IMAGE_NAME .
docker push $YOUR_IMAGE_NAME
```

### Modify Pipeline and Util Files for Distributed Training

First, modify the `_cifar10_root` in `cifar10_pipeline_native_keras` to point to a remote directory (For example, `gs://YOUR_GCS_PATH`),
and upload the CIFAR10 base directory there when you are done modifying the files. This allows training worker pods to pull the utility files
from your remote directory during training.

Then, specify the custom Trainer executor `kubernetes_trainer_executor.GenericExecutor` imported from `tfx.extensions.google_cloud_kubernetes.trainer`:

```
  trainer = Trainer(
    module_file=module_file,
    custom_executor_spec=executor_spec.ExecutorClassSpec(kubernetes_trainer_executor.GenericExecutor),
    examples=transform.outputs['transformed_examples'],
    transform_graph=transform.outputs['transform_graph'],
    schema=schema_gen.outputs['schema'],
    train_args=trainer_pb2.TrainArgs(num_steps=160),
    eval_args=trainer_pb2.EvalArgs(num_steps=4),
    custom_config={
      kubernetes_trainer_executor.TRAINING_ARGS_KEY: {
        `tfx_image`: None, # SPECIFY CUSTOM IMAGE (IF ANY)
        'num_workers': 1, # SPECIFY NUMBER OF WORKERS HERE
        'num_gpus_per_worker': 0} # SPECIFY NUMBER OF GPUs HERE
      }
    )
```

You should specify the training resources you wish to use in `custom_config`. Note that this should be consistent with the Node Pool you created in step 1.
If you are using a custom image, supply it under `tfx_image`.

Finally, replace `cifar10_utils_native_keras` with the one in this directory. You may need to edit `_LABEL_MAP_FILE_PATH` in the file to point to your remote path.

You should then be able to execute your pipeline with distributed training:
```
python ~/cifar10/cifar_pipeline_native_keras.py
```

## Recommendations

The following has been tested to yield the best speed-up results compared to training on a single node:

- Multi-worker training with 4 or 8 replicas with 8 or 16 nodes, >= 64 GB memory
- Single worker training with GPU (i.e. NVIDIA K80)

If configured correctly, the above two configurations should yield a 60% to 70% speed up in wall time versus single worker with no GPU. If you need an even higher speed up (up to 80%),
consider using multi-worker training with 1 GPU per node. However, cost efficiency will be lower, as the training is bottlenecked by preprocessing of images on CPU.