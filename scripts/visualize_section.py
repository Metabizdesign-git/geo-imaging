"""section_boundaries 기반 2D 단면도 이미지 생성.

to_section_json() 출력(경계선 polyline)을 matplotlib로 렌더링하여 PNG로 저장한다.
"""

import matplotlib
matplotlib.use("Agg")

from pathlib import Path

import matplotlib.pyplot as plt


def save_section_image(section_data: dict, output_path: str | Path) -> Path:
    """단면 경계선 데이터를 2D 이미지로 저장한다.

    Args:
        section_data: to_section_json() 반환 dict.
        output_path: 출력 PNG 파일 경로.

    Returns:
        저장된 파일의 Path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    cmap = plt.colormaps["tab10"]

    for i, bd in enumerate(section_data["boundaries"]):
        pts = bd["points"]
        h_vals = [p[0] for p in pts]
        v_vals = [p[1] for p in pts]
        color = cmap(i % 10)
        label = f"{bd['upper']} / {bd['lower']}"
        ax.plot(h_vals, v_vals, color=color, linewidth=2, label=label)

    h_min, h_max = section_data["h_range"]
    v_min, v_max = section_data["v_range"]
    ax.set_xlim(h_min, h_max)
    ax.set_ylim(v_min, v_max)

    ax.set_xlabel(f"{section_data['h_axis']} (m)")
    ax.set_ylabel(f"{section_data['v_axis']} (m)")
    ax.set_title(f"{section_data['axis']} section @ {section_data['position']}")
    if section_data["boundaries"]:
        ax.legend(loc="best")
    ax.grid(True, alpha=0.3)

    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")
    return output_path


def save_all_sections(result, output_dir: str | Path = "results") -> list[Path]:
    """ModelResult에서 xz, yz, xy 3개 단면 이미지를 생성한다.

    Args:
        result: 계산된 ModelResult 객체.
        output_dir: 출력 디렉터리.

    Returns:
        저장된 파일 경로 리스트.
    """
    from gempygen import to_section_json

    output_dir = Path(output_dir)
    saved = []

    for axis in ("xz", "yz", "xy"):
        section = to_section_json(result, axis=axis)
        path = output_dir / f"section_{axis}.png"
        save_section_image(section, path)
        saved.append(path)

    return saved


if __name__ == "__main__":
    from gempygen import GeoModelBuilder, BoreholeLayer

    result = (
        GeoModelBuilder("simple_model")
        .set_extent(0, 100, 0, 100, -300, 0)
        .set_resolution(50, 50, 50)
        .add_borehole(0, 0, [
            BoreholeLayer(element="Sandstone", z=-100),
            BoreholeLayer(element="Limestone", z=-200),
        ])
        .add_borehole(100, 0, [
            BoreholeLayer(element="Sandstone", z=-120),
            BoreholeLayer(element="Limestone", z=-220),
        ])
        .add_borehole(0, 100, [
            BoreholeLayer(element="Sandstone", z=-110),
            BoreholeLayer(element="Limestone", z=-210),
        ])
        .build_and_compute()
    )

    saved = save_all_sections(result, output_dir="results")
    print(f"\n  Done! {len(saved)} images saved.")
