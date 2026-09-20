def _get_media_event_data(
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    event_file_path: str,
    event_file_type: int,
) -> dict[str, str]:
    _, config_entry = dr.async_get_device_and_config_entry_for_domain(
        hass, device.id, domain=DOMAIN
    )
    if config_entry is None or config_entry.state is not ConfigEntryState.LOADED:
        return {}
    config_entry_id = config_entry.entry_id

    coordinator: MotionEyeUpdateCoordinator = config_entry.runtime_data
    client = coordinator.client

    for identifier in device.identifiers:
        data = split_motioneye_device_identifier(identifier)
        if data is not None:
            camera_id = data[2]
            camera = get_camera_from_cameras(camera_id, coordinator.data)
            break
    else:
        return {}

    root_directory = camera.get(KEY_ROOT_DIRECTORY) if camera else None
    if root_directory is None:
        return {}

    kind = "images" if client.is_file_type_image(event_file_type) else "movies"

    # The file_path in the event is the full local filesystem path to the
    # media. To convert that to the media path that motionEye will
    # understand, we need to strip the root directory from the path.
    try:
        if os.path.commonpath([root_directory, event_file_path]) != root_directory:
            return {}
    except ValueError:
        return {}

    file_path = "/" + os.path.relpath(event_file_path, root_directory)
    output = {
        EVENT_MEDIA_CONTENT_ID: (
            f"{URI_SCHEME}{DOMAIN}/{config_entry_id}#{device.id}#{kind}#{file_path}"
        ),
    }
    proxy_path = _build_media_proxy_path(
        config_entry_id,
        camera_id,
        kind,
        file_path,
        preview=False,
    )

    try:
        base_url = get_url(hass)
    except NoURLAvailableError:
        return output

    output[EVENT_FILE_URL] = base_url + async_sign_path(
        hass,
        proxy_path,
        timedelta(minutes=5),
        use_content_user=True,
    )
    return output
