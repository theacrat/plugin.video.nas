import datetime

from apis.StremioAPI import stremio_api
from classes.StremioLibrary import StremioLibrary
from classes.StremioMeta import Video, StremioMeta, StremioType
from modules.utils import thread_function, log


def player_update(
    content_id,
    content_type,
    video_id,
    curr_time,
    total_time,
    playing,
    start_stop,
):
    meta = stremio_api.get_metadata_by_id(content_id, content_type)
    episode: Video | None = None

    if video_id != meta.id:
        episode = next(v for v in meta.videos if v.id == video_id)

    meta.library.update_progress(curr_time, total_time, video_id)

    if start_stop:
        meta.library.start_stop(video_id, episode)

    meta.library.push()

    trakt_event = {
        "eventName": "traktPlaying" if playing else "traktPaused",
        "player": {
            "hasTrakt": True,
            "libItemID": meta.id,
            "libItemName": meta.name,
            "libItemTimeDuration": total_time,
            "libItemTimeOffset": curr_time,
            "libItemType": meta.type,
            "libItemVideoID": video_id,
        },
    }
    stremio_api.send_events([trakt_event])


def get_continue_watching():
    def _library_to_meta(l: StremioLibrary):
        return stremio_api.get_metadata_by_id(l.id, l.type)

    def _check_date_time(last_watched, released):
        if released is None:
            return False
        if last_watched is None:
            return True

        now = datetime.datetime.now(datetime.timezone.utc)

        return last_watched < released < now

    data_store = stremio_api.get_data_store()
    results = {
        k: v
        for k, v in data_store.items()
        if v.type != StremioType.OTHER
        and (v.temp or not v.removed)
        and v.state.timeOffset > 0
    }

    notif_results = {
        k: v
        for k, v in data_store.items()
        if not v.state.noNotif
        and v.type not in [StremioType.OTHER, StremioType.MOVIE]
        and not v.removed
        and not v.temp
        and not k in results
    }

    items = [
        *thread_function(_library_to_meta, list(results.values())),
        *stremio_api.get_notifications(list(notif_results.values())),
    ]

    metas = sorted(
        [e for e in items if e.library.mtime is not None],
        key=lambda e: (
            max(
                next((v.released for v in reversed(e.videos) if v.aired), None)
                or datetime.datetime.fromtimestamp(0).astimezone(datetime.timezone.utc),
                e.library.mtime,
            )
        ),
        reverse=True,
    )

    return [
        i
        for i in metas
        if not (
            i.id in notif_results and i.behaviorHints and i.behaviorHints.defaultVideoId
        )
        and not (
            i.id in notif_results
            and not any(
                _check_date_time(i.library.state.lastWatched, v.released)
                for v in i.videos
                if v.season
            )
        )
    ]


def set_library_status(content_id, content_type, status):
    meta = stremio_api.get_metadata_by_id(content_id, content_type)
    meta.library.set_library_status(status)


def clear_progress(content_id, content_type):
    meta = stremio_api.get_metadata_by_id(content_id, content_type)
    meta.library.clear_progress()


def dismiss_notification(content_id, content_type):
    meta = stremio_api.get_metadata_by_id(content_id, content_type)
    meta.library.dismiss_notification()


def mark_watched(content_id, content_type, status, video_id=None):
    meta = stremio_api.get_metadata_by_id(content_id, content_type)
    meta.library.mark_watched(status, video_id)
