"""Phase 6 — the advertised Telegram Desktop version must match the MTProto
layer actually spoken on the wire.

Telethon announces a layer in `InvokeWithLayer`; a real Telegram Desktop build
of version X always announces the specific layer that shipped with X. Claiming
a version whose layer disagrees with the one on the wire is a fingerprint
mismatch that no amount of device randomization hides.

`TELEGRAM_DESKTOP_LAYERS` maps each release in `TELEGRAM_DESKTOP_VERSIONS` to
the layer read from `Telegram/SourceFiles/mtproto/scheme/api.tl` at that tag.
"""
from __future__ import annotations

import pytest
from opentele.api import API

TD = API.TelegramDesktop


def test_every_version_has_a_layer() -> None:
    missing = [v for v in TD.TELEGRAM_DESKTOP_VERSIONS if v not in TD.TELEGRAM_DESKTOP_LAYERS]
    assert not missing, f"versions without a known layer: {missing}"


def test_no_orphan_layer_entries() -> None:
    """Every layer entry belongs to a version we actually advertise."""
    orphans = [v for v in TD.TELEGRAM_DESKTOP_LAYERS if v not in TD.TELEGRAM_DESKTOP_VERSIONS]
    assert not orphans, f"layer entries for unknown versions: {orphans}"


def test_layers_are_monotonic_with_version_order() -> None:
    """The list is newest-first, so layers must never increase as we walk it."""
    layers = [TD.TELEGRAM_DESKTOP_LAYERS[v] for v in TD.TELEGRAM_DESKTOP_VERSIONS]
    assert layers == sorted(layers, reverse=True), (
        "TELEGRAM_DESKTOP_VERSIONS must stay ordered newest-first: "
        f"layers came out as {layers}"
    )


def test_telethon_layer_is_readable() -> None:
    """The installed Telethon must expose its layer — the whole alignment
    mechanism silently degrades to 'no filtering' if this ever breaks."""
    assert isinstance(TD._telethon_layer(), int)


def test_default_app_version_matches_telethon_layer() -> None:
    """The default is realigned at import, so it holds for any supported Telethon.

    A failure here means `_align_desktop_version_with_telethon()` did not run or
    the table lost the entry it picked.
    """
    layer = TD._telethon_layer()
    bare = TD.app_version.removesuffix(" x64")
    assert TD.TELEGRAM_DESKTOP_LAYERS.get(bare) == layer, (
        f"default app_version {TD.app_version!r} speaks layer "
        f"{TD.TELEGRAM_DESKTOP_LAYERS.get(bare)}, but Telethon announces {layer}. "
        f"Candidates: {TD._versions_for_layer(layer)}"
    )


def test_default_app_version_is_newest_for_that_layer() -> None:
    """Of the builds on our layer, advertise the newest — an old patch release
    of the right layer is still an odd thing to be running."""
    layer = TD._telethon_layer()
    assert TD.app_version == f"{TD._versions_for_layer(layer)[0]} x64"


def test_realignment_is_idempotent() -> None:
    """Running the import-time alignment again must not drift the value."""
    from opentele.api import _align_desktop_version_with_telethon

    before = TD.app_version
    _align_desktop_version_with_telethon()
    assert TD.app_version == before


def test_generate_matches_telethon_layer() -> None:
    """Generated versions are layer-consistent by default."""
    layer = TD._telethon_layer()
    for i in range(25):
        bare = TD._generate_tdesktop_app_version(unique_id=f"uid-{i}").removesuffix(" x64")
        assert TD.TELEGRAM_DESKTOP_LAYERS[bare] == layer, (
            f"{bare} speaks layer {TD.TELEGRAM_DESKTOP_LAYERS[bare]}, telethon {layer}"
        )


def test_match_layer_false_widens_the_pool() -> None:
    """Opting out gives access to versions outside the current layer."""
    layer = TD._telethon_layer()
    picked = {
        TD._generate_tdesktop_app_version(unique_id=f"wide-{i}", match_layer=False)
        .removesuffix(" x64")
        for i in range(60)
    }
    assert len(picked) > len(TD._versions_for_layer(layer)), (
        "match_layer=False should draw from the whole table"
    )


def test_versions_for_layer_exact_match_wins() -> None:
    assert TD._versions_for_layer(227) == ["6.9.3", "6.9.2", "6.9.1", "6.9.0"]
    assert TD._versions_for_layer(228) == [
        "7.0.8", "7.0.7", "7.0.6", "7.0.5", "7.0.4", "7.0.3", "7.0.2", "7.0.1",
    ]


def test_versions_for_layer_falls_back_below_when_unknown() -> None:
    """A Telethon newer than this table must not fall back to ancient builds:
    it picks the highest layer that does not overshoot."""
    assert TD._versions_for_layer(999) == [
        "7.0.8", "7.0.7", "7.0.6", "7.0.5", "7.0.4", "7.0.3", "7.0.2", "7.0.1",
    ]


def test_versions_for_layer_with_ancient_layer_returns_oldest_entries() -> None:
    """A Telethon older than the whole table must land on the OLDEST builds.

    Returning the full table here would let a client speaking layer 180
    advertise a 7.0.x build — the exact mismatch this mapping exists to stop.
    """
    assert TD._versions_for_layer(1) == ["6.0.2", "6.0.1", "6.0.0"]


def test_versions_for_layer_none_returns_full_table() -> None:
    assert TD._versions_for_layer(None) == list(TD.TELEGRAM_DESKTOP_VERSIONS)


def test_no_beta_versions_in_table() -> None:
    """Betas report differently; advertising a beta-only build is a tell.
    These were all `prerelease: true` on GitHub when the table was built."""
    betas = {"7.0.0", "6.9.4", "6.8.5", "6.8.4", "6.8.3", "6.7.7", "6.6.4",
             "6.6.3", "6.4.4", "6.4.3", "6.3.10", "6.2.6", "6.2.5", "6.0.3"}
    present = betas.intersection(TD.TELEGRAM_DESKTOP_VERSIONS)
    assert not present, f"beta builds must not be advertised: {sorted(present)}"


@pytest.mark.parametrize("version", ["7.0.8", "7.0.1", "6.9.3", "6.8.2", "6.0.0"])
def test_known_layer_values(version: str) -> None:
    """Spot-check against api.tl at the matching release tag.

    6.9.3 and 7.0.1 straddle the 227 -> 228 boundary: the newest stable still on
    227 and the oldest already on 228 (7.0.0 is a beta, so it is not in the
    table). Getting either wrong shifts every layer lookup around the cutover.
    """
    expected = {"7.0.8": 228, "7.0.1": 228, "6.9.3": 227, "6.8.2": 225, "6.0.0": 211}
    assert TD.TELEGRAM_DESKTOP_LAYERS[version] == expected[version]
