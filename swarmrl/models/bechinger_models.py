from swarmrl.models.interaction_model import InteractionModel
import numpy as np


class Lavergne2019(InteractionModel):
    """
    See doi/10.1126/science.aau5347
    """

    def __init__(self, vision_half_angle=np.pi / 2., act_force=1, perception_threshold=1):
        self.vision_half_angle = vision_half_angle
        self.act_force = act_force
        self.perception_threshold = perception_threshold

    def calc_force(self, colloid, other_colloids) -> np.ndarray:
        # determine perception value
        colls_in_vision = get_colloids_in_vision(colloid, other_colloids, vision_half_angle=self.vision_half_angle)
        perception = 0
        my_pos = np.copy(colloid.pos)
        for coll in colls_in_vision:
            dist = np.linalg.norm(my_pos - coll.pos)
            perception += 1 / (2 * np.pi * dist)

        # set activity on/off
        if perception >= self.perception_threshold:
            my_director = np.copy(colloid.director)
            return self.act_force * my_director / np.linalg.norm(my_director)
        else:
            return np.zeros((3,))

    def calc_torque(self, colloid, other_colloids) -> np.ndarray:
        return np.zeros((3,))


class Baeuerle2020(InteractionModel):
    """
    See https://doi.org/10.1038/s41467-020-16161-4
    """

    def __init__(self,
                 act_force=1.,
                 detection_radius_position=1.,
                 detection_radius_orientation=1.,
                 vision_half_angle=np.pi / 2.,
                 angular_deviation=1,
                 ):
        self.act_force = act_force
        self.detection_radius_position = detection_radius_position
        self.detection_radius_orientation = detection_radius_orientation
        self.vision_half_angle = vision_half_angle
        self.angular_deviation = angular_deviation

    def _calc_force(self, colloid, other_colloids) -> np.ndarray:
        """
        Needs to be used by the new direction aswell
        """
        # get vector to center of mass
        colls_in_vision_pos = get_colloids_in_vision(colloid,
                                                     other_colloids,
                                                     vision_half_angle=self.vision_half_angle,
                                                     vision_range=self.detection_radius_position)
        if len(colls_in_vision_pos) == 0:
            # not detailed in the paper. take from previous model
            return np.zeros((3,))

        com = np.mean(np.stack([col.pos for col in colls_in_vision_pos] ,axis=1), axis=1)
        to_com = com - colloid.pos
        to_com_angle = angle_from_vector(to_com)

        # get average orientation of neighbours
        colls_in_vision_orientation = get_colloids_in_vision(colloid,
                                                             other_colloids,
                                                             vision_half_angle=self.vision_half_angle,
                                                             vision_range=self.detection_radius_orientation)

        if len(colls_in_vision_orientation) == 0:
            # not detailed in paper
            return np.zeros((3,))

        mean_orientation_in_vision = np.mean(np.stack([col.director for col in colls_in_vision_orientation],
                                                      axis=1),
                                             axis=1)
        mean_orientation_in_vision /= np.linalg.norm(mean_orientation_in_vision)

        # choose new orientation based on self.angular_deviation
        new_angle_choices = [to_com_angle + self.angular_deviation, to_com_angle - self.angular_deviation]
        new_orientation_choices = [vector_from_angle(ang) for ang in new_angle_choices]

        angle_deviations = [np.arccos(np.dot(new_orient, mean_orientation_in_vision)) for new_orient in
                            new_orientation_choices]
        new_orientation = new_orientation_choices[np.argmin(angle_deviations)]

        return self.act_force * new_orientation

    def calc_force(self, colloid, other_colloids) -> np.ndarray:
        return self._calc_force(colloid, other_colloids)

    def calc_new_direction(self, colloid, other_colloids) -> np.ndarray:
        force = self._calc_force(colloid, other_colloids)
        return force/np.linalg.norm(force)

    def calc_torque(self, colloid, other_colloids) -> np.ndarray:
        return np.zeros((3,))


def get_colloids_in_vision(coll, other_coll, vision_half_angle=np.pi, vision_range=np.inf) -> list:
    my_pos = np.array(coll.pos)
    my_director = coll.director
    colls_in_vision = []
    for other_p in other_coll:
        dist = other_p.pos - my_pos
        dist_norm = np.linalg.norm(dist)
        in_range = dist_norm < vision_range
        in_front = np.arccos(np.dot(dist / dist_norm, my_director)) < vision_half_angle
        if in_front and in_range:
            colls_in_vision.append(other_p)
    return colls_in_vision


def angle_from_vector(vec) -> float:
    return np.arctan2(vec[1], vec[0])


def vector_from_angle(angle) -> np.ndarray:
    return np.array([np.cos(angle), np.sin(angle), 0])