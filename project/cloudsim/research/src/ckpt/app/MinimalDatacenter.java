package ckpt.app;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.LinkedList;
import java.util.List;

import org.cloudbus.cloudsim.Cloudlet;
import org.cloudbus.cloudsim.CloudletSchedulerSpaceShared;
import org.cloudbus.cloudsim.Datacenter;
import org.cloudbus.cloudsim.DatacenterBroker;
import org.cloudbus.cloudsim.DatacenterCharacteristics;
import org.cloudbus.cloudsim.Host;
import org.cloudbus.cloudsim.Log;
import org.cloudbus.cloudsim.Pe;
import org.cloudbus.cloudsim.Storage;
import org.cloudbus.cloudsim.UtilizationModelFull;
import org.cloudbus.cloudsim.Vm;
import org.cloudbus.cloudsim.VmAllocationPolicySimple;
import org.cloudbus.cloudsim.VmSchedulerTimeShared;
import org.cloudbus.cloudsim.core.CloudSim;
import org.cloudbus.cloudsim.provisioners.BwProvisionerSimple;
import org.cloudbus.cloudsim.provisioners.PeProvisionerSimple;
import org.cloudbus.cloudsim.provisioners.RamProvisionerSimple;

/**
 * Setup check with STOCK CloudSim 3.0.3 classes only: one datacenter, 2 hosts (1 PE, 1000 MIPS),
 * 2 VMs, 4 cloudlets (2 per VM, space-shared so they run one after another).
 * Expected: all 4 cloudlets SUCCESS; on each VM the first finishes at ~L1/1000 s and the second at
 * ~(L1+L2)/1000 s after start.
 */
public class MinimalDatacenter {

    public static void main(String[] args) throws Exception {
        Log.disable();
        CloudSim.init(1, Calendar.getInstance(), false);

        List<Host> hosts = new ArrayList<Host>();
        for (int h = 0; h < 2; h++) {
            List<Pe> pes = new ArrayList<Pe>();
            pes.add(new Pe(0, new PeProvisionerSimple(1000)));
            hosts.add(new Host(h, new RamProvisionerSimple(4096), new BwProvisionerSimple(10000), 1000000, pes,
                    new VmSchedulerTimeShared(pes)));
        }
        DatacenterCharacteristics ch = new DatacenterCharacteristics("x86", "Linux", "Xen", hosts, 0.0, 0, 0, 0, 0);
        new Datacenter("DC_0", ch, new VmAllocationPolicySimple(hosts), new LinkedList<Storage>(), 0);

        DatacenterBroker broker = new DatacenterBroker("Broker");
        List<Vm> vms = new ArrayList<Vm>();
        for (int v = 0; v < 2; v++) {
            vms.add(new Vm(v, broker.getId(), 1000, 1, 1024, 1000, 10000, "Xen", new CloudletSchedulerSpaceShared()));
        }
        long[] lengths = {400000, 200000, 300000, 100000};   // MI -> 400, 200, 300, 100 s at 1000 MIPS
        List<Cloudlet> cls = new ArrayList<Cloudlet>();
        for (int c = 0; c < lengths.length; c++) {
            Cloudlet cl = new Cloudlet(c, lengths[c], 1, 300, 300, new UtilizationModelFull(),
                    new UtilizationModelFull(), new UtilizationModelFull());
            cl.setUserId(broker.getId());
            cl.setVmId(c % 2);
            cls.add(cl);
        }
        broker.submitVmList(vms);
        broker.submitCloudletList(cls);

        CloudSim.startSimulation();
        List<Cloudlet> done = broker.getCloudletReceivedList();
        CloudSim.stopSimulation();

        System.out.println("Cloudlet  Status   VM  Start      Finish     ExecTime");
        int ok = 0;
        for (Cloudlet c : done) {
            boolean success = c.getCloudletStatus() == Cloudlet.SUCCESS;
            ok += success ? 1 : 0;
            // (VM-to-host mapping is not printed: the stock broker destroys VMs at the end of the run)
            System.out.printf("%8d  %-7s %3d  %9.2f  %9.2f  %8.2f%n", c.getCloudletId(),
                    success ? "SUCCESS" : "FAILED", c.getVmId(),
                    c.getExecStartTime(), c.getFinishTime(), c.getActualCPUTime());
        }
        System.out.println("Completed " + ok + "/" + lengths.length + " cloudlets successfully");
        if (ok != lengths.length) {
            System.exit(1);
        }
    }
}
