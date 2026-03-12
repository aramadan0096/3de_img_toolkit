#
# 3DE4.script.name: Image Toolkit
#
# 3DE4.script.gui: Main Window::R Tools
#
# 3DE4.script.comment: Launches img_toolkit.py through a proxy bootstrap.
#


def main():
    import ImgToolkitProxyInit

    ImgToolkitProxyInit.bootstrap()


if __name__ == "__main__":
    main()
