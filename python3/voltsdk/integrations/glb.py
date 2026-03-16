"""GLB / 3D visualization utilities.

Provides :func:`view_glb` for rendering GLTF/GLB models either in a
Jupyter notebook (using k3d) or in a desktop window (using VTK).

This module provides interactive rendering helpers for GLB assets.
"""

from __future__ import annotations

import os


def view_glb(file_path: str):
    """Render a GLB file interactively.

    In a Jupyter notebook, uses **k3d** for inline 3D rendering.
    Otherwise, opens a **VTK** desktop render window.

    Parameters
    ----------
    file_path:
        Path to the ``.glb`` file.

    Returns
    -------
    k3d.Plot or vtk.vtkRenderWindowInteractor
        The interactive plot/interactor object.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    ImportError
        If required dependencies (vtk, k3d) are not installed.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f'File not found: {file_path}')

    try:
        import vtk
    except ImportError as exc:
        raise ImportError(
            'vtk is required to view GLB files. '
            'Install with: pip install "voltsdk[visualization]"'
        ) from exc

    reader = vtk.vtkGLTFReader()
    reader.SetFileName(file_path)
    reader.Update()

    # Detect Jupyter notebook environment
    in_notebook = False
    try:
        from IPython import get_ipython
        shell = get_ipython()
        in_notebook = (
            shell is not None
            and shell.__class__.__name__ == 'ZMQInteractiveShell'
        )
    except Exception:
        pass

    if in_notebook:
        try:
            import k3d
        except ImportError as exc:
            raise ImportError(
                'k3d is required in notebook mode. '
                'Install with: pip install k3d'
            ) from exc

        plot = k3d.plot()
        multi_block = reader.GetOutput()
        iterator = multi_block.NewIterator()
        iterator.InitTraversal()
        while not iterator.IsDoneWithTraversal():
            item = iterator.GetCurrentDataObject()
            if item is not None:
                plot += k3d.vtk_poly_data(item, color=0x222222)
            iterator.GoToNextItem()

        try:
            from IPython.display import display as ipython_display
            ipython_display(plot)
        except Exception:
            pass

        return plot

    # Desktop VTK render window
    mapper = vtk.vtkCompositePolyDataMapper2()
    mapper.SetInputDataObject(reader.GetOutput())

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    renderer = vtk.vtkRenderer()
    renderer.AddActor(actor)
    renderer.SetBackground(0.07, 0.07, 0.07)

    render_window = vtk.vtkRenderWindow()
    render_window.AddRenderer(renderer)
    render_window.SetSize(1200, 800)
    render_window.SetWindowName(os.path.basename(file_path))

    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)

    render_window.Render()
    interactor.Initialize()
    interactor.Start()

    return interactor
