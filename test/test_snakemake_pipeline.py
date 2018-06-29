# Copyright (c) 2018. Mount Sinai School of Medicine
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import getpass
import json
import glob
from os import chdir, listdir
from os.path import dirname, join
from shutil import copy2
import tempfile
import unittest

import snakemake

from docker.run_snakemake import main as docker_entrypoint, default_vaxrank_targets

class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workdir = tempfile.TemporaryDirectory()
        cls.referencedir = tempfile.TemporaryDirectory()
        cls.inputdir = tempfile.TemporaryDirectory()
        cls.config_tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=True)
        cls.make_test_config()
        cls.populate_test_files()

    @classmethod
    def tearDownClass(cls):
        cls.referencedir.cleanup()
        cls.workdir.cleanup()
        cls.inputdir.cleanup()
        cls.config_tmpfile.close()

    @classmethod
    def populate_test_files(cls):
        # populate reference files with random crap
        with open(join(cls.referencedir.name, 'b37decoy.fasta.gz'), 'w') as genome:
            genome.write('placeholder')
        with open(join(cls.referencedir.name, 'transcripts.gtf.gz'), 'w') as transcripts:
            transcripts.write('placeholder')
        with open(join(cls.referencedir.name, 'dbsnp.vcf.gz'), 'w') as dbsnp:
            dbsnp.write('placeholder')
        with open(join(cls.referencedir.name, 'cosmic.vcf'), 'w') as cosmic:
            cosmic.write('placeholder')
        for path in glob.glob('datagen/*.fastq.gz'):
            copy2(path, cls.inputdir.name)


    @classmethod
    def make_test_config(cls):
        with open(join(cls._get_test_dir_path(), 'idh1_config.json'), 'r') as idh1_config_file:
            config_file_contents = idh1_config_file.read()
        # kinda gross, but: replace /outputs, /reference-genome, /inputs paths in config file with
        # temp dir locations
        config_file_contents = config_file_contents.replace(
            '/outputs', cls.workdir.name).replace(
            '/reference-genome/b37decoy', cls.referencedir.name).replace(
            '/inputs', cls.inputdir.name)
        cls.config_tmpfile.write(config_file_contents)
        cls.config_tmpfile.seek(0)

    @classmethod
    def _get_test_dir_path(cls):
        return dirname(__file__)

    @classmethod
    def _get_snakemake_dir_path(cls):
        return join(cls._get_test_dir_path(), '..', 'snakemake')

    # This simulates a dry run on the test data, and mostly checks rule graph validity.
    def test_workflow_compiles(self):
        chdir(self._get_snakemake_dir_path())
        self.assertTrue(snakemake.snakemake(
            'Snakefile',
            cores=20,
            resources={'mem_mb': 160000},
            configfile=self.config_tmpfile.name,
            config={'num_threads': 22},
            dryrun=True,
            printshellcmds=True,
            targets=[
                join(
                    self.workdir.name, 
                    'idh1-test-sample',
                    'vaccine-peptide-report_netmhcpan-iedb_mutect-strelka.txt'),
                join(
                    self.workdir.name,
                    'idh1-test-sample',
                    'rna_final.bam'),
                ],
            stats=join(self.workdir.name, 'idh1-test-sample', 'stats.json')
        ))

    def test_docker_entrypoint_script(self):
        cli_args = [
            '--configfile', self.config_tmpfile.name,
            '--dry-run',
            '--target', join(
                self.workdir.name, 
                'idh1-test-sample',
                'rna_final.bam'),  # valid target
        ]
        # run to make sure it doesn't crash
        docker_entrypoint(cli_args)

        # check that invalid target fails
        fake_target_cli_args = [
            '--configfile', self.config_tmpfile.name,
            '--dry-run',
            '--target', join(
                self.workdir.name, 
                'idh1-test-sample',
                'fakey_fakerson'),
        ]
        self.assertRaises(ValueError, docker_entrypoint, fake_target_cli_args)

        bad_vaxrank_target_cli_args = [
            '--configfile', self.config_tmpfile.name,
            '--dry-run',
            '--target', join(
                self.workdir.name, 
                'idh1-test-sample',
                'vaccine-peptide-report_netmhcpan-iedb_mutect-strelka-mutect2.txt'),
        ]
        self.assertRaises(ValueError, docker_entrypoint, bad_vaxrank_target_cli_args)
