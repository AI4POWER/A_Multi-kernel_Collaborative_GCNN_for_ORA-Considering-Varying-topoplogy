# -*- coding: utf-8 -*-
"""
Created on Tuesday, January 9 10:18:04 2024

@author: maosheng
"""
import numpy as np
from pypower.ext2int import ext2int
from pypower.idx_gen import GEN_BUS, PG, QG, VG, QMAX, QMIN, GEN_BUS, GEN_STATUS, PMAX, PMIN
from pypower.idx_brch import PF, QF, BR_STATUS, RATE_A, RATE_B, RATE_C, BR_R, BR_B, BR_X, T_BUS, F_BUS, MU_SF, MU_ST, MU_ANGMIN, MU_ANGMAX, PT
import os
import torch
import torch.nn as nn
import torch.optim as optim

import csv, copy
import numpy as np
from scipy.sparse import csr_matrix, hstack, vstack

def save_csv(data, file_path):
    filename = file_path
    data = np.array(data)
    if len(data.shape) < 2:
        data = data[:, np.newaxis]
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(data)


def read_csv(file_path):
    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        data = list(reader)
    # 将数字转化为 float 形式
    for row in data:
        for i in range(len(row)):
            try:
                row[i] = float(row[i])
            except ValueError:
                pass  # 如果无法转换为 float，保留原始字符串

    return np.array(data)


class CNN(nn.Module):
    def __init__(self, ):
        super(CNN, self).__init__()

        self.conv1 = nn.Sequential(
            # 输入[1,28,28]
            nn.Conv2d(
                in_channels=1,  # 输入图片的高度
                out_channels=16,  # 输出图片的高度
                kernel_size=3,  # 5x5的卷积核，相当于过滤器
                stride=(2, 1),  # 卷积核在图上滑动，每隔一个扫一次
                padding=2,  # 给图外边补上0
            ),
            # 经过卷积层 输出[16,28,28] 传入池化层
            nn.ReLU(),
            nn.Conv2d(
                in_channels=16,  # 输入图片的高度
                out_channels=16,  # 输出图片的高度
                kernel_size=3,  # 5x5的卷积核，相当于过滤器
                stride=(2, 2),  # 卷积核在图上滑动，每隔一个扫一次
                padding=2,  # 给图外边补上0
            ),
            nn.ReLU(),
            nn.Conv2d(
                in_channels=16,  # 输入图片的高度
                out_channels=16,  # 输出图片的高度
                kernel_size=3,  # 5x5的卷积核，相当于过滤器
                stride=(2, 2),  # 卷积核在图上滑动，每隔一个扫一次
                padding=2,  # 给图外边补上0
            ),
            nn.ReLU(),
            nn.Conv2d(
                in_channels=16,  # 输入图片的高度
                out_channels=16,  # 输出图片的高度
                kernel_size=3,  # 5x5的卷积核，相当于过滤器
                stride=(2, 2),  # 卷积核在图上滑动，每隔一个扫一次
                padding=2,  # 给图外边补上0
            ),
        ).to(device)

        self.faltten = nn.Flatten().to(device)

        self.predictor = nn.Sequential(
            nn.Linear(2112, 1000),
            nn.ReLU(),
            nn.Linear(1000, 1000),
            nn.ReLU(),
            nn.Linear(1000, 661),
            # nn.Sigmoid()
        ).to(device)

    def forward(self, ef):
        ef1 = self.conv1(ef)
        ef = self.faltten(ef1)

        cut = self.predictor(ef)
        return cut

def load_data(data_dir):
    # 读取原始数据
    data = np.load(data_dir, allow_pickle=True)
    input_G = data['input_G_sparse']
    input_B = data['input_B_sparse']
    input_Pd = data['input_Pd']
    input_Qd = data['input_Qd']
    output_cut = data['output_cut']

    input_Gen = data['input_Gen']

    node_num = input_Pd.shape[1]
    sample_num = input_Pd.shape[0]

    # 处理没有不能直接读取的数据
    input_e = np.ones((sample_num, node_num, 1))
    input_f = np.zeros((sample_num, node_num, 1))

    input_G_diag = np.zeros((sample_num, node_num, 1))
    input_B_diag = np.zeros((sample_num, node_num, 1))
    input_G_ndiag = copy.deepcopy(input_G)
    input_B_ndiag = copy.deepcopy(input_G)
    for i in range(sample_num):
        G = input_G[i].todense()
        B = input_B[i].todense()
        input_G_diag[i, :, :] = np.diag(G)[:, np.newaxis]
        input_B_diag[i, :, :] = np.diag(B)[:, np.newaxis]
        input_G_ndiag[i] = csr_matrix(G - np.diag(np.diag(G)))
        input_B_ndiag[i] = csr_matrix(B - np.diag(np.diag(B)))

    input_G_diag = np.array(input_G_diag)
    input_B_diag = np.array(input_B_diag)
    input_G_ndiag = np.array(input_G_ndiag)
    input_B_ndiag = np.array(input_B_ndiag)

    # input_G_diag = np.array([np.diag(input_G[i].todense())[:, np.newaxis] for i in range(sample_num)])
    # input_B_diag = np.array([np.diag(input_B[i].todense())[:, np.newaxis] for i in range(sample_num)])
    # input_G_ndiag = np.array(
    #     [csr_matrix(input_G[i].todense() - np.diag(input_G_diag[i, :, 0])) for i in range(sample_num)])
    # input_B_ndiag = np.array(
    #     [csr_matrix(input_B[i].todense() - np.diag(input_B_diag[i, :, 0])) for i in range(sample_num)])

    return (input_e, input_f, input_G, input_B, input_G_diag, input_B_diag, input_G_ndiag, input_B_ndiag,
            input_Pd, input_Qd, input_Gen, output_cut)



def preprocess(mpc, data_dir, all_data=False):
    (input_e, input_f, input_G, input_B, input_G_diag, input_B_diag, input_G_ndiag, input_B_ndiag, input_Pd, input_Qd,
     input_Gen, output_cut) = load_data(data_dir)

    # 对数据进行预处理
    output_cut[output_cut < 0.000001] = 0
    input_Gen = input_Gen[:, :, np.newaxis]
    input_Pd = input_Pd[:, :, np.newaxis] / 100
    input_Qd = input_Qd[:, :, np.newaxis] / 100

    # 剔除拓扑改变时，系统解裂，只有一个节点独立的情况
    temp = np.abs(input_G_diag[:, :, 0]) + np.abs(input_B_diag[:, :, 0])
    temp = np.min(temp, -1)
    idx = np.where(temp > 1)[0]
    print("训练样本数量：", idx.shape[0])

    (input_e, input_f, input_G, input_B, input_G_diag, input_B_diag, input_G_ndiag, input_B_ndiag, input_Pd, input_Qd,
     input_Gen, output_cut) = (input_e[idx, :, :], input_f[idx, :, :], input_G[idx], input_B[idx],
                               input_G_diag[idx, :, :], input_B_diag[idx, :, :], input_G_ndiag[idx],
                               input_B_ndiag[idx],
                               input_Pd[idx, :, :], input_Qd[idx, :, :], input_Gen[idx, :, :], output_cut[idx, :])

    # 对切负荷量进行归一化处理
    output_cut = output_cut / input_Pd[:, :, 0]
    output_cut[np.isnan(output_cut)] = 0
    output_cut[np.isinf(output_cut)] = 0
    input_Pd_orginal = copy.deepcopy(input_Pd)

    # 获取部分参数
    sample_num = input_Pd.shape[0]
    bus_num = input_Pd.shape[1]
    In = np.eye(bus_num)

    A = np.zeros((mpc['bus'].shape[0], mpc['gen'].shape[0]))
    for i in range(mpc['gen'].shape[0]):
        for j in range(mpc['bus'].shape[0]):
            if mpc['gen'][i, GEN_BUS] == mpc['bus'][j, 0]:
                A[j, i] = 1

    input_Pg = np.zeros(input_Pd.shape)
    input_Qg = np.zeros(input_Pd.shape)
    for i in range(input_Pd.shape[0]):
        Pg = mpc['gen'][:, PMAX][:, np.newaxis] * input_Gen[i, :, :] / 100
        input_Pg[i, :, :] = np.dot(A, Pg)
        Qg = mpc['gen'][:, QMAX][:, np.newaxis] * input_Gen[i, :, :] / 100
        input_Qg[i, :, :] = np.dot(A, Qg)

    # 构建输入特征向量
    input_pq_Bdiag = np.concatenate([input_Pd, input_Qd, input_Pg, input_Qg, input_B_diag, input_G_diag], axis=-1)[:, np.newaxis, :, :]

    if all_data:
        return [input_pq_Bdiag, output_cut], input_Pd_orginal[:, :, 0]
    else:
        return [input_pq_Bdiag[:20000, :, :], output_cut[:20000, :]], [
        input_pq_Bdiag[30000:, :, :], output_cut[30000:, :]], input_Pd_orginal[:20000, :, 0], input_Pd_orginal[30000:, :, 0]


def data_generator(train_data, batch_size=15):
    (input_pq_Bdiag, output_cut) = train_data
    idx = np.random.permutation(input_pq_Bdiag.shape[0])
    for k in range(int(np.ceil(input_pq_Bdiag.shape[0] / batch_size))):
        from_idx = k * batch_size
        to_idx = (k + 1) * batch_size
        index = idx[from_idx:to_idx]
        # input_e, input_f, input_G, input_B, input_G_diag, input_B_diag, input_Pd, input_Qd
        inputs_ = input_pq_Bdiag[index, :, :]
        outputs_ = output_cut[index, :]

        yield inputs_, outputs_


def Z_Score(trainData):
    trainData = np.array(trainData)
    mean_train = np.mean(trainData, axis=0)
    std_train = np.std(trainData, axis=0)
    std_train = std_train + 0.0000001
    trainData = (trainData - mean_train)
    trainData = trainData / std_train
    trainData[np.isnan(trainData)] = 0
    trainData[np.isinf(trainData)] = 0
    # trainData = 1/(1+np.exp(-1*trainData))
    return trainData, mean_train, std_train


if __name__ == '__main__':
    # 配置环境变量是否使用GPU
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    ################################## set device ##################################
    print("============================================================================================")
    # set device to cpu or cuda
    device = torch.device('cpu')
    if (torch.cuda.is_available()):
        device = torch.device('cuda:0')
        torch.cuda.empty_cache()
        print("Device set to : " + str(torch.cuda.get_device_name(device)))
    else:
        print("Device set to : cpu")
    print("============================================================================================")

    # 加载IEEE 39节点系统数据
    from pypower.case118 import case118
    import matplotlib.pyplot as plt

    # from utils import *
    from pypower.loadcase import loadcase
    mpc = loadcase('./dataset/case661')
    A = np.zeros((mpc['bus'].shape[0], mpc['gen'].shape[0]))
    for i in range(mpc['gen'].shape[0]):
        for j in range(mpc['bus'].shape[0]):
            if mpc['gen'][i, GEN_BUS] == mpc['bus'][j, 0]:
                A[j, i] = 1

    # 导入训练数据
    data = np.load('./dataset/case_661_testing_dist[1.0_0.5]_sample[20000].npz', allow_pickle=True)
    input_Pd = data['input_Pd'][:, :, np.newaxis]/100
    input_Qd = data['input_Qd'][:, :, np.newaxis]/100
    output_cut = data['output_cut']
    input_Gen = data['input_Gen'][:, :, np.newaxis]
    input_Br = data['input_Br']
    input_G = data['input_G']
    input_B = data['input_B']

    node_num = input_Pd.shape[1]
    sample_num = input_Pd.shape[0]

    input_G_diag = np.zeros((sample_num, node_num, 1))
    input_B_diag = np.zeros((sample_num, node_num, 1))
    for i in range(sample_num):
        G = input_G[i].todense()
        B = input_B[i].todense()
        input_G_diag[i, :, :] = np.diag(G)[:, np.newaxis]
        input_B_diag[i, :, :] = np.diag(B)[:, np.newaxis]

    input_G_diag = np.array(input_G_diag)
    input_B_diag = np.array(input_B_diag)


    input_Pg = np.zeros(input_Pd.shape)
    input_Qg = np.zeros(input_Pd.shape)
    for i in range(input_Pd.shape[0]):
        Pg = mpc['gen'][:, PMAX][:, np.newaxis] * input_Gen[i, :, :] / 100
        input_Pg[i, :, :] = np.dot(A, Pg)
        Qg = mpc['gen'][:, QMAX][:, np.newaxis] * input_Gen[i, :, :] / 100
        input_Qg[i, :, :] = np.dot(A, Qg)

    inputs = np.concatenate([input_Pd, input_Qd, input_Pg, input_Qg, input_B_diag, input_G_diag], axis=-1)[:, np.newaxis, :, :]

    output_cut = output_cut / input_Pd[:, :, 0]
    output_cut[np.isnan(output_cut)] = 0
    output_cut[np.isinf(output_cut)] = 0

    train_data = [inputs, output_cut]


    # 导入测试数据
    data = np.load('./dataset/case_661_sparse_Data.npz', allow_pickle=True)
    input_Pd = data['input_Pd'][:, :, np.newaxis]/100
    input_Qd = data['input_Qd'][:, :, np.newaxis]/100
    output_cut = data['output_cut']
    input_Gen = data['input_Gen'][:, :, np.newaxis]
    input_Br = data['input_Br']
    input_G = data['input_G']
    input_B = data['input_B']

    node_num = input_Pd.shape[1]
    sample_num = input_Pd.shape[0]

    input_G_diag = np.zeros((sample_num, node_num, 1))
    input_B_diag = np.zeros((sample_num, node_num, 1))
    for i in range(sample_num):
        G = input_G[i].todense()
        B = input_B[i].todense()
        input_G_diag[i, :, :] = np.diag(G)[:, np.newaxis]
        input_B_diag[i, :, :] = np.diag(B)[:, np.newaxis]

    input_G_diag = np.array(input_G_diag)
    input_B_diag = np.array(input_B_diag)

    input_Pg = np.zeros(input_Pd.shape)
    input_Qg = np.zeros(input_Pd.shape)
    for i in range(input_Pd.shape[0]):
        Pg = mpc['gen'][:, PMAX][:, np.newaxis] * input_Gen[i, :, :] / 100
        input_Pg[i, :, :] = np.dot(A, Pg)
        Qg = mpc['gen'][:, QMAX][:, np.newaxis] * input_Gen[i, :, :] / 100
        input_Qg[i, :, :] = np.dot(A, Qg)

    inputs = np.concatenate([input_Pd, input_Qd, input_Pg, input_Qg, input_B_diag, input_G_diag], axis=-1)[:,
             np.newaxis, :, :]

    output_cut = output_cut / input_Pd[:, :, 0]
    output_cut[np.isnan(output_cut)] = 0
    output_cut[np.isinf(output_cut)] = 0

    test_data = [inputs, output_cut]

    # 计算基准值
    output_cut_eval = test_data[1]
    p = np.sum(output_cut_eval, axis=1)
    idx = np.where(p > 0.001)[0]
    lolp0 = idx.shape[0] / p.shape[0]
    EENS0 = np.sum(output_cut_eval) * 100 / test_data[0].shape[0] * 8760

    input_pq_Bdiag, mean_, std_ = Z_Score(train_data[0])
    temp = (test_data[0] - mean_) / std_
    temp[np.isnan(temp)] = 0
    temp[np.isinf(temp)] = 0
    train_data[0] = torch.tensor(input_pq_Bdiag, dtype=torch.float32).to(device)
    train_data[1] = torch.tensor(train_data[1], dtype=torch.float32).to(device)
    test_data[0] = torch.tensor(temp, dtype=torch.float32).to(device)
    test_data[1] = torch.tensor(test_data[1], dtype=torch.float32).to(device)

    # train_data[0] = torch.tensor(train_data[0], dtype=torch.float32).to(device)
    # train_data[1] = torch.tensor(train_data[1], dtype=torch.float32).to(device)
    # test_data[0] = torch.tensor(test_data[0], dtype=torch.float32).to(device)
    # test_data[1] = torch.tensor(test_data[1], dtype=torch.float32).to(device)

    # 构建神经网络，并配置训练参数
    model = CNN()
    lossfun = nn.L1Loss()
    # lossfun = nn.MSELoss()
    # optimizer = optim.SGD(model.parameters(), lr=0.001, momentum=0.5)
    optimizer = optim.Adam(model.parameters(), lr=0.0001)
    # optimizer = optim.Adam(model.parameters(), lr=0.001)

    saved_folder = "./models/M9/"
    if (not os.path.exists(saved_folder)):
        os.mkdir(saved_folder)
    # model.load_state_dict(torch.load("./models/M9/Torch_Model.pth"))
    # 进行训练
    # epoch_num = 1000
    # losses_train = []
    # losses_test = []
    # for epoch in range(epoch_num):  # loop over the dataset multiple times
    #     epoch_loss = []
    #     for fs, labels in data_generator(train_data, batch_size=100):
    #         optimizer.zero_grad()
    #         outputs = model(fs)
    #         # loss = lossfun(outputs, labels)
    #         loss = torch.mean(torch.multiply(torch.abs(outputs - labels), labels + 1))
    #         loss.backward()
    #         optimizer.step()
    #
    #         epoch_loss.append(loss.item())
    #
    #     # 训练完成之后使用测试集进行测试
    #     res = model(test_data[0])
    #     error = lossfun(res, test_data[1])
    #     # res[res>1] = 1
    #     # res[res<0] = 0
    #     output_cut = res.detach().cpu().numpy()*input_Pd[:, :, 0]
    #
    #     p = np.sum(output_cut, axis=1)
    #     idx = np.where(p > 0.01)[0]
    #     lolp1 = idx.shape[0] / p.shape[0]
    #     EENS1 = np.sum(output_cut) * 100 / test_data[0].shape[0] * 8760
    #
    #     e_lolp = abs(lolp1 - lolp0) / lolp0
    #     e_eens = abs(EENS1 - EENS0) / EENS0
    #
    #     # res = res.detach().cpu().numpy() * input_Pd_original_testing
    #     # label = test_data[1].detach().cpu().numpy() * input_Pd_original_testing
    #
    #
    #     # 保存loss、accuracy值，可用于可视化
    #     losses_train.append(np.mean(epoch_loss))
    #     losses_test.append(error.item())
    #
    #     # 每一个epoch后打印Loss、Accuracy以及花费的时间
    #     print("Epoch {:03d}: Train Loss: {:.6f}, Test Loss: {:.6f}".format(epoch, np.mean(epoch_loss), error), lolp1, e_lolp, EENS1, e_eens)
    #
    #     if epoch % 10 == 0:
    #         # 训练完成后更新保存模型
    #         model_path = saved_folder + "/Torch_Model.pth"
    #         torch.save(model.state_dict(), model_path)
    #
    #         # 保存训练过程的损失值
    #         temp = np.concatenate([np.array(losses_train)[:, np.newaxis], np.array(losses_test)[:, np.newaxis]],
    #                               axis=-1)
    #         save_csv(temp, saved_folder + "/train_and_test_losses.csv")
    #
    # print('finish!')

    model.load_state_dict(torch.load("./models/M9/Torch_Model.pth"))

    import time
    t1 = time.time()

    res = model(test_data[0]).detach().cpu().numpy()
    res[res<0.0001] = 0
    res[res>1] = 1
    output_cut_ = res * input_Pd[:, :, 0]
    output_cut_[output_cut_ < 0.0001] = 0
    p = np.sum(output_cut_, axis=1)
    idx = np.where(p > 0)[0]
    lolp1 = idx.shape[0] / p.shape[0]
    EENS1 = np.sum(output_cut_) * 100 / test_data[0].shape[0] * 8760

    t2 = time.time()


    output_cut_eval = test_data[1].detach().cpu().numpy()*input_Pd[:, :, 0]
    output_cut_eval[output_cut_eval<0.001] = 0
    p = np.sum(output_cut_eval, axis=1)
    idx = np.where(p > 0)[0]
    lolp0 = idx.shape[0] / p.shape[0]
    EENS0 = np.sum(output_cut_eval) * 100 / test_data[0].shape[0] * 8760

    e_lolp = abs(lolp1 - lolp0) / lolp0
    e_eens = abs(EENS1 - EENS0) / EENS0
    print(lolp1, e_lolp, EENS1, e_eens)
    print(lolp0, EENS0)
    print(t2-t1)
