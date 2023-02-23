#!/usr/bin/env python3

# - Check for arguments
# - Download and install custom maps
# - Download and replace configuration files
# - End execution

# Argument Examples: 
# --maps=s3://fastdl.syd.s3.aws.jacobtaylor.id.au/gmod/maps
# --config=s3://configuration.syd.s3.aws.jacobtaylor.id.au/gmod

import sys
import bz2
import json
import shutil
import argparse
import tempfile

from os.path import basename
from pathlib import Path
from functools import cached_property
from urllib.parse import urlparse
from typing import Optional, Generator, Any, BinaryIO
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError


@dataclass
class S3Path:
    bucket: str
    key: str

    @property
    def base_name(self):
        return basename(self.key)

    @classmethod
    def from_url(cls, url: str):
        result = urlparse(url)

        if result.scheme == "s3" and result.netloc is not None:
            return cls(result.netloc, result.path)
    
        return None
    
    @classmethod
    def from_object(cls, bucket: str, object: dict):
        return cls(bucket, object["Key"])
    
    @property
    def _s3_kwargs(self):
        return {
            "Bucket": self.bucket,
            "Key": self.key
        }

    def ls(self, client) -> Generator["S3Path", Any, Any]:
        paginator = client.paginator("list_objects_v2")
  
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.key):
            yield from map(self.from_object, page["Contents"])

    def get(self, client, fd: BinaryIO):
        client.download_fileobj(self.bucket, self.key, fd)

    def load_json(self, client):
        response = client.get_object(**self._s3_kwargs)
        return json.load(response["Body"])

    def is_object(self, client):
        try: 
            client.head_object(**self._s3_kwargs)
        except ClientError as e:
            return False
        return True
    
    def navigate(self, *args):
        elements = self.key.split("/")
        new_path = "/".join(elements + list(args))
        return type(self)(self.bucket, f"/{new_path}" )
    
    @property
    def url(self):
        return f"s3://{self.bucket}{self.key}"


@dataclass
class RuntimeContext:
    map_location: Optional[S3Path]
    config_location: Optional[S3Path]
    working_dir: Path
    home_dir: Path
    session: boto3.Session = boto3.Session()

    @property
    def is_maps_provided(self):
        return self.map_location is not None
    
    @property
    def is_config_provided(self):
        return self.config_location is not None
    
    @classmethod
    def from_urls(cls, map_url, config_url):
        return cls(
            S3Path.from_url(map_url),
            S3Path.from_url(config_url),
            Path.cwd().resolve(),
            Path.home().resolve()
        )
    
    @cached_property
    def s3(self):
        return boto3.client("s3")
    
    @property
    def maps(self):
        for obj in self.map_location.ls(self.s3):
            if obj.key.endswith(".bsp.bz2"):
                yield obj

    @property
    def map_dir(self):
        return self.working_dir / "maps"
    
    @property
    def static_manifest_path(self):
        return self.home_dir / "manifest.json"
    
    @property
    def config_manifest(self) -> dict[str, str]:
        dynamic_manifest = self.config_location.navigate("manifest.json")
        if dynamic_manifest.is_object(self.s3):
            return dynamic_manifest.load_json(self.s3)
        with self.static_manifest_path.open() as fd:
            return json.load(fd)

    def download_map(self, tmpdir: Path, obj: S3Path):
            tmpfile = tmpdir / obj.base_name
            mapfile = self.map_dir / obj.base_name

            with tmpfile.open("wb") as fd:
                obj.get(self.s3, fd)
            with bz2.BZ2File(tmpfile) as bz2_fd, mapfile.open("rb") as bsp_fd:
                shutil.copyfileobj(bz2_fd, bsp_fd)

    def download_maps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir).resolve()
            for obj in self.maps:
                self.download_map(tmpdir, obj)

    def download_configuration_file(self, filename: str, directory: str):
        target_path = self.working_dir / directory / filename
        source_path = self.config_location.navigate(filename)
        with target_path.open("wb") as fd:
            source_path.get(self.s3, fd)

    def download_configuration_files(self):
        for filename, directory in self.config_manifest.items():
            self.download_configuration_file(filename, directory)


def parse_args() -> RuntimeContext:
    parser = argparse.ArgumentParser()

    parser.add_argument("--maps", type=str, default="")
    parser.add_argument("--config", type=str, default="")

    args = parser.parse_args()

    return RuntimeContext.from_urls(args.maps, args.config)


def main():
    print("Beginning server configuration...")
    ctx = parse_args()

    if ctx.is_maps_provided:
        print(f"Downloading custom maps from repository: {ctx.map_location.url}")
        ctx.download_maps()
    else:
        print("Skipping custom map download - no map repository provided")

    if ctx.is_config_provided:
        print(f"Downloading dynamic configuration from repository: {ctx.config_location.url}")
        ctx.download_configuration_files()
    else:
        print("Skipping dynamic configuration - no configuration repository provided")

    print("Server configuration successful - starting SRCDS...")
    return 0

if __name__ == "__main__":
    sys.exit(main())