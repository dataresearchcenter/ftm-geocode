from followthemoney.proxy import EntityProxy
from openaleph_procrastinate import defer
from openaleph_procrastinate.app import make_app
from openaleph_procrastinate.model import DatasetJob
from openaleph_procrastinate.tasks import task

from ftm_geocode.geocode import geocode_proxy
from ftm_geocode.settings import Settings

settings = Settings()
app = make_app(__loader__.name)
ORIGIN = "ftm-geocode"


@task(app=app)
def geocode(job: DatasetJob) -> None:
    entities: list[EntityProxy] = []
    with job.get_writer() as bulk:
        for entity in job.get_entities():
            for result in geocode_proxy(settings.geocoders, entity, rewrite_ids=False):
                bulk.put(result, origin=ORIGIN)
                entities.append(result)
    defer.index(app, job.dataset, entities, **job.context)
