from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])

class ReceiverSimulationConfig(BaseModel):
    simulate_prepare_crash_before_vote: bool = False
    simulate_commit_fail_before_apply: bool = False
    simulate_commit_crash: bool = False
    simulate_rollback_crash_after_apply: bool = False
    simulate_delay_ms: int = 0

# Global state to hold the configuration
_receiver_simulation_state = ReceiverSimulationConfig()

@router.get("/receiver", response_model=ReceiverSimulationConfig)
def get_receiver_simulation():
    return _receiver_simulation_state

@router.post("/receiver", response_model=ReceiverSimulationConfig)
def set_receiver_simulation(config: ReceiverSimulationConfig):
    global _receiver_simulation_state
    _receiver_simulation_state = config
    return _receiver_simulation_state

def get_current_receiver_simulation() -> ReceiverSimulationConfig:
    return _receiver_simulation_state
