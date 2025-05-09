# Use as an OpenAleph service

`ftm-geocode` can be used as an **OpenAleph** service to geocode ingested entities.

Refer to the [`openaleph-procrastinate`](https://openaleph.org/docs/lib/openaleph-procrastinate/) documentation about the service, task queue and worker logic.

## Run the worker

```bash
export PROCRASTINATE_APP=ftm_geocode.tasks.app
procrastinate worker -q ftm-geocode
```

## Defer tasks from other services

```python
from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob

app = make_app()

def defer_job(entity):
    with app.open():
        job = DatasetJob.from_entity(
            dataset="my_dataset",
            queue="ftm-geocode",
            task="ftm_geocode.tasks.geocode",
            entity=entity
        )
        job.defer()
```

[Read more about this example](https://openaleph.org/docs/lib/openaleph-procrastinate/howto/)
