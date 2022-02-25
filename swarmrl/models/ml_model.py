"""
Espresso interaction model capable of handling a neural network as a function.
"""

import typing

import numpy as np
import torch
import torch.nn.functional
from torch.distributions import Categorical

from swarmrl.models.interaction_model import Action, Colloid, InteractionModel
from swarmrl.observables.observable import Observable
from swarmrl.networks.network import Network


class MLModel(InteractionModel):
    """
    Class for a NN based espresso interaction model.
    """

    def __init__(
        self, model: Network, observable: Observable
    ):
        """
        Constructor for the NNModel.

        Parameters
        ----------
        model : Network
                A SwarmRl model to use in the action computation.
        observable : Observable
                A method to compute an observable given a current system state.
        """
        super().__init__()
        self.model = model
        self.observable = observable

        translate = Action(force=10.0)
        rotate_clockwise = Action(torque=np.array([0.0, 0.0, 0.1]))
        rotate_counter_clockwise = Action(torque=np.array([0.0, 0.0, -0.1]))
        do_nothing = Action()

        self.actions = {
            "RotateClockwise": rotate_clockwise,
            "Translate": translate,
            "RotateCounterClockwise": rotate_counter_clockwise,
            "DoNothing": do_nothing,
        }

    def calc_action(self, colloids: typing.List[Colloid]) -> typing.List[Action]:
        """
        Compute the state of the system based on the current colloid position.

        In the case of the ML models, this method undertakes the following steps:

        1. Compute observable
        2. Compute action probabilities
        3. Compute action

        Returns
        -------
        action: Action
                Return the action the colloid should take.
        """
        actions = []
        for colloid in colloids:
            other_colloids = [c for c in colloids if c is not colloid]
            feature_vector = self.observable.compute_observable(colloid, other_colloids)

            action_probabilities = torch.nn.functional.softmax(
                self.model(feature_vector), dim=-1
            )
            action_distribution = Categorical(action_probabilities)
            action_idx = action_distribution.sample()
            # action_log_prob = action_distribution.log_prob(action_idx)

            actions.append(self.actions[list(self.actions)[action_idx.item()]])

        return actions
