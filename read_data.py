from torch.utils.data import Dataset
import torch
import torch.nn.functional as F
from os.path import join
import os

import sys
if os.path.exists('/opt/ros/kinetic/lib/python2.7/dist-packages'):
    sys.path.remove('/opt/ros/kinetic/lib/python2.7/dist-packages')
import cv2

import numpy as np
import torchvision.transforms as transforms
import png
from PIL import Image

class KITTI2015(Dataset):

    def __init__(self, directory, mode, validate_size=40, occ=True, transform=None):
        super().__init__()

        self.mode = mode
        self.transform = transform

        if mode == 'train' or mode == 'validate':
            self.dir = join(directory, 'training')
        elif mode == 'test':
            self.dir = join(directory, 'testing')

        left_dir = join(self.dir, 'image_2')
        right_dir = join(self.dir, 'image_3')
        left_imgs = list()
        right_imgs = list()

        if mode == 'train':
            imgs_range = range(200 - validate_size)
        elif mode == 'validate':
            imgs_range = range(200 - validate_size, 200)
        elif mode == 'test':
            imgs_range = range(200)

        fmt = '{:06}_10.png'

        for i in imgs_range:
            left_imgs.append(join(left_dir, fmt.format(i)))
            right_imgs.append(join(right_dir, fmt.format(i)))

        self.left_imgs = left_imgs
        self.right_imgs = right_imgs

        # self.disp_imgs = None
        if mode == 'train' or mode == 'validate':
            disp_imgs = list()
            if occ:
                disp_dir = join(self.dir, 'disp_occ_0')
            else:
                disp_dir = join(self.dir, 'disp_noc_0')
            disp_fmt = '{:06}_10.png'
            for i in imgs_range:
                disp_imgs.append(join(disp_dir, disp_fmt.format(i)))

            self.disp_imgs = disp_imgs


    def __len__(self):
        return len(self.left_imgs)


    def __getitem__(self, idx):
        data = {}

        # bgr mode
        data['left'] = cv2.imread(self.left_imgs[idx])
        data['right'] = cv2.imread(self.right_imgs[idx])
        if self.mode != 'test':
            data['disp'] = loadPNG16(self.disp_imgs[idx])
         # data['disp'] = cv2.imread(self.left_imgs[idx])[:, :, 0].transpose(2, 0, 1)
        if self.transform:
            # data['left'] = self.transform(data['left'])
            # data['right'] = self.transform(data['right'])
            # print(self.left_imgs[idx])
            data = self.transform(data)
        return data

def loadPNG16(file):
    pngReader = png.Reader(filename=file)
    pngData = pngReader.read()[2]
    npImage = np.vstack(map(np.uint16, pngData))

    return npImage.astype(np.float32) / 256.0

class RandomCrop():

    def __init__(self, output_size):
        self.output_size = output_size

    def __call__(self, sample):
        new_h, new_w = self.output_size
        h, w, _ = sample['left'].shape
        top = np.random.randint(0, h - new_h)
        left = np.random.randint(0, w - new_w)

        for key in sample:
            sample[key] = sample[key][top: top + new_h, left: left + new_w]

        return sample


class Normalize():
    '''
    RGB mode
    '''

    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def __call__(self, sample):
        sample['left'] = sample['left'] / 255.0
        sample['right'] = sample['right'] / 255.0

        sample['left'] = self.__normalize(sample['left'])
        sample['right'] = self.__normalize(sample['right'])

        return sample

    def __normalize(self, img):
        for i in range(3):
            img[:, :, i] = (img[:, :, i] - self.mean[i]) / self.std[i]
        return img


class ToTensor():

    def __call__(self, sample):
        left = sample['left']
        right = sample['right']
        disp = sample['disp']
        # H x W x C ---> C x H x W
        sample['left'] = torch.from_numpy(left.transpose([2, 0, 1])).type(torch.FloatTensor)
        sample['right'] = torch.from_numpy(right.transpose([2, 0, 1])).type(torch.FloatTensor)
        sample['disp'] = torch.from_numpy(disp).type(torch.FloatTensor)
        # if 'disp' in sample:
        #     sample['disp'] = torch.from_numpy(sample['disp']).type(torch.FloatTensor)

        return sample


class Pad():
    def __init__(self, H, W):
        self.w = W
        self.h = H

    def __call__(self, sample):
        pad_h = self.h - sample['left'].size(1)
        pad_w = self.w - sample['left'].size(2)

        left = sample['left'].unsqueeze(0)  # [1, 3, H, W]
        left = F.pad(left, pad=(0, pad_w, 0, pad_h))
        right = sample['right'].unsqueeze(0)  # [1, 3, H, W]
        right = F.pad(right, pad=(0, pad_w, 0, pad_h))
        disp = sample['disp'].unsqueeze(0).unsqueeze(1)  # [1, 1, H, W]
        disp = F.pad(disp, pad=(0, pad_w, 0, pad_h))

        sample['left'] = left.squeeze()
        sample['right'] = right.squeeze()
        sample['disp'] = disp.squeeze()

        return sample


if __name__ == '__main__':
    import torchvision.transforms as T
    from torch.utils.data import DataLoader
    # BGR
    mean = [0.406, 0.456, 0.485]
    std = [0.225, 0.224, 0.229]

    train_transform = T.Compose([transforms.ToTensor(),transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))])
    train_dataset = KITTI2015('H:/lc\scene_flow', mode='train', transform=train_transform)
    train_loader = DataLoader(train_dataset)
    print(len(train_loader))

    validate_transform = T.Compose([ToTensor(), Normalize(mean, std), Pad(384, 1248)])
    validate_dataset = KITTI2015('H:/lc\scene_flow', mode='validate', transform=validate_transform)
    validate_loader = DataLoader(validate_dataset, batch_size=1, num_workers=1)


    for i, batch in enumerate(validate_loader):
        target_disp = batch['disp']
        mask = (target_disp > 0)
        mask