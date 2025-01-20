import datetime

from apis.StremioAPI import stremio_api
from classes.StremioLibrary import StremioLibrary
from classes.StremioMeta import Video, StremioMeta
from modules.kodi_utils import timestamp_zone_format_switcher, dataclass_to_dict


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
    def _check_date_time(last_watched, released):
        if not released:
            return False
        if not last_watched:
            return True

        released_time = datetime.datetime.fromisoformat(
            timestamp_zone_format_switcher(released)
        )
        last_watched_time = datetime.datetime.fromisoformat(
            timestamp_zone_format_switcher(last_watched)
        )
        now = datetime.datetime.now(datetime.timezone.utc)

        return last_watched_time < released_time < now

    data_store = stremio_api.get_data_store()
    results = {
        k: v
        for k, v in data_store.items()
        if v.type != "other" and (v.temp or not v.removed) and v.state.timeOffset > 0
    }

    notif_results = {
        k: v
        for k, v in data_store.items()
        if not v.state.noNotif
        and v.type not in ["other", "movie"]
        and not v.removed
        and not v.temp
        and not k in results
    }

    all_results: list[StremioLibrary] = [
        *results.values(),
        *stremio_api.get_notifications(notif_results.values()),
    ]

    metas = sorted(
        [
            StremioMeta.from_dict({"id": e.id, **dataclass_to_dict(e)})
            for e in all_results
        ],
        key=lambda e: e.library.modified_time,
        reverse=True,
    )

    return [
        i
        for i in metas
        if not (i.id in notif_results and i.behaviorHints.defaultVideoId)
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


def mark_watched(content_id, content_type, video_id, status):
    meta = stremio_api.get_metadata_by_id(content_id, content_type)
    meta.library.mark_watched(video_id, status)
