def test_descarga_datos_package_importable() -> None:
    import descarga_datos

    assert descarga_datos.__file__
