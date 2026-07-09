from pydantic import BaseModel, Field


class BinaryRequirement(BaseModel):
    name: str = Field(min_length=1)
    min_version: str | None = None
    version_args: list[str] = Field(default_factory=lambda: ["--version"])


class ProfileConfig(BaseModel):
    enabled_checks: list[str] = Field(default_factory=list)
    required_binaries: list[BinaryRequirement] = Field(default_factory=list)
    permission_paths: list[str] = Field(default_factory=list)
    shell_config_files: list[str] = Field(default_factory=list)


class DotDoctorConfig(BaseModel):
    profiles: dict[str, ProfileConfig]


def default_config() -> DotDoctorConfig:
    common_checks = [
        "binary.python",
        "binary.pip",
        "binary.git",
        "binary.gcc",
        "binary.g++",
        "binary.cmake",
        "binary.make",
        "path.integrity",
        "shell.config",
        "permissions.dev_dirs",
    ]

    return DotDoctorConfig(
        profiles={
            "python-dev": ProfileConfig(
                enabled_checks=common_checks,
                required_binaries=[
                    BinaryRequirement(name="python", min_version="3.11"),
                    BinaryRequirement(name="pip"),
                    BinaryRequirement(name="git", min_version="2.30"),
                    BinaryRequirement(name="gcc", min_version="10.0"),
                    BinaryRequirement(name="g++", min_version="10.0"),
                    BinaryRequirement(name="cmake", min_version="3.20"),
                    BinaryRequirement(name="make"),
                ],
                permission_paths=["~", "."],
                shell_config_files=["~/.bashrc", "~/.zshrc"],
            ),
            "cpp-dev": ProfileConfig(
                enabled_checks=common_checks,
                required_binaries=[
                    BinaryRequirement(name="python", min_version="3.11"),
                    BinaryRequirement(name="pip"),
                    BinaryRequirement(name="git", min_version="2.30"),
                    BinaryRequirement(name="gcc", min_version="11.0"),
                    BinaryRequirement(name="g++", min_version="11.0"),
                    BinaryRequirement(name="cmake", min_version="3.22"),
                    BinaryRequirement(name="make"),
                ],
                permission_paths=["~", "."],
                shell_config_files=["~/.bashrc", "~/.zshrc"],
            ),
        }
    )
