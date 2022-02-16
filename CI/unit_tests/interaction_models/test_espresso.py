import pathlib as pl
import tempfile
import unittest as ut

import context
import h5py
import numpy as np
import pint

from swarmrl.engine import espresso
from swarmrl.models import dummy_models


class EspressoTest(ut.TestCase):
    def assertIsFile(self, path):
        if not pl.Path(path).resolve().is_file():
            raise AssertionError("File does not exist: %s" % str(path))

    def test_class(self):
        """
        Sadly, espresso systems are global so we have to do all tests on only one object
        """
        ureg = pint.UnitRegistry()
        params = espresso.MDParams(
            n_colloids=2,
            ureg=ureg,
            colloid_radius=ureg.Quantity(1, "micrometer"),
            fluid_dyn_viscosity=ureg.Quantity(8.9e-3, "pascal * second"),
            WCA_epsilon=ureg.Quantity(1e-20, "joule"),
            colloid_density=ureg.Quantity(2.65, "gram / centimeter**3"),
            temperature=ureg.Quantity(0, "kelvin"),
            box_length=ureg.Quantity(10000, "micrometer"),
            time_step=ureg.Quantity(0.05, "second"),
            time_slice=ureg.Quantity(0.1, "second"),
            write_interval=ureg.Quantity(0.1, "second"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = espresso.EspressoMD(
                params, out_folder=temp_dir, write_chunk_size=1
            )
            self.assertListEqual(runner.colloids, [])

            runner.setup_simulation()
            self.assertEqual(len(runner.system.part[:]), params.n_colloids)

            part_data_old = runner.get_particle_data()

            # rotate all particles along one axis
            direc = np.array([1 / np.sqrt(3), 1 / np.sqrt(3), 1 / np.sqrt(3)])
            rotator = dummy_models.ToConstDirection(direc)
            runner.integrate(1, rotator)
            runner.system.time = 0.0
            directors = runner.get_particle_data()["Directors"]
            for dir_ in directors:
                np.testing.assert_array_almost_equal(dir_, direc)

            n_slices = 15
            force = 1.234
            force_model = dummy_models.ConstForce(force)
            runner.integrate(n_slices, force_model)

            self.assertIsFile(f"{temp_dir}/trajectory.hdf5")
            self.assertIsFile(f"{temp_dir}/simulation_log.log")

            part_data_new = runner.get_particle_data()
            time_new = runner.system.time

            # plausibility-tests for velocity and position because too lazy to do the actual calculation
            # friction must be the same for all particles and all directions
            gamma = runner.colloid_friction_translation
            new_vel = part_data_new["Velocities"]
            new_vel_shouldbe = force * direc / gamma
            for vel in new_vel:
                np.testing.assert_array_almost_equal(vel, new_vel_shouldbe)

            old_pos = part_data_old["Unwrapped_Positions"]
            new_pos = part_data_new["Unwrapped_Positions"]
            self.assertTrue(not np.any(new_pos == old_pos))

            # time must be the same for all particles and all directions
            time_passed = (new_pos - old_pos) / new_vel
            np.testing.assert_array_almost_equal(time_passed, time_passed[0, 0])

            # write_interval == time_slice -> one output per slice
            # writing happens before integrating -> run one more
            runner.integrate(1, force_model)
            with h5py.File(f"{temp_dir}/trajectory.hdf5", "r") as h5_file:
                part_group = h5_file["colloids"]
                np.testing.assert_array_almost_equal(
                    part_group["Unwrapped_Positions"][-1, :, :], new_pos
                )
                np.testing.assert_array_almost_equal(
                    part_group["Velocities"][-1, :, :], new_vel
                )
                self.assertAlmostEqual(part_group["Times"][-1, 0, 0], time_new)
                self.assertSetEqual(
                    set(part_group.keys()),
                    {"Unwrapped_Positions", "Velocities", "Times", "Directors"},
                )


if __name__ == "__main__":
    ut.main()
