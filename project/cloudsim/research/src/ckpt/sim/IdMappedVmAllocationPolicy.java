package ckpt.sim;

import java.util.List;
import java.util.Map;

import org.cloudbus.cloudsim.Host;
import org.cloudbus.cloudsim.Vm;
import org.cloudbus.cloudsim.VmAllocationPolicySimple;

/**
 * Places each VM on a pre-assigned host (VM i -> host i), so that the mapping
 * "Backblaze drive -> simulated host -> VM -> work stream" is deterministic.
 */
public final class IdMappedVmAllocationPolicy extends VmAllocationPolicySimple {
    private final Map<Integer, Host> hostOfVm;

    public IdMappedVmAllocationPolicy(List<? extends Host> hosts, Map<Integer, Host> hostOfVm) {
        super(hosts);
        this.hostOfVm = hostOfVm;
    }

    @Override
    public boolean allocateHostForVm(Vm vm) {
        Host h = hostOfVm.get(vm.getId());
        return h != null && allocateHostForVm(vm, h);
    }
}
